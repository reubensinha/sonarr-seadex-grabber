"""
ID Mapping service for converting between TVDB, AniList, and other anime database IDs.
Uses the Kometa Anime-IDs and Anime-Lists repositories for accurate mappings.
"""

import json
import os
import time
from typing import Dict, List, Optional
from xml.etree import ElementTree as ET

import requests

from core.config import DATA_DIR
from core.utils import log


class AnimeIDMapper:
    """Service for mapping between different anime database IDs."""

    def __init__(self):
        self.kometa_ids_url = "https://raw.githubusercontent.com/Kometa-Team/Anime-IDs/master/anime_ids.json"
        self.anime_lists_url = "https://raw.githubusercontent.com/Anime-Lists/anime-lists/master/anime-list-master.xml"

        # Cache file paths (respects the configurable DATA_DIR so custom
        # data locations, e.g. a Docker volume mount, stay consistent)
        data_dir = DATA_DIR if isinstance(DATA_DIR, str) else "data"
        self.cache_dir = os.path.join(data_dir, "id_mappings")
        os.makedirs(self.cache_dir, exist_ok=True)

        self.kometa_cache_file = os.path.join(self.cache_dir, "kometa_anime_ids.json")
        self.anime_lists_cache_file = os.path.join(self.cache_dir, "anime_lists.xml")

        # In-memory caches
        self._kometa_mappings: Dict = {}
        self._anime_lists_mappings: Dict = {}

        # Cache validity (24 hours)
        self.cache_max_age = 24 * 60 * 60

    def _is_cache_valid(self, cache_file: str) -> bool:
        """Check if cache file exists and is not older than cache_max_age."""
        if not os.path.exists(cache_file):
            return False

        file_age = time.time() - os.path.getmtime(cache_file)
        return file_age < self.cache_max_age

    def _download_kometa_ids(self) -> bool:
        """Download Kometa anime IDs mapping from GitHub."""
        try:
            log("Downloading Kometa anime IDs mapping...")
            response = requests.get(self.kometa_ids_url, timeout=30)
            response.raise_for_status()

            with open(self.kometa_cache_file, "w", encoding="utf-8") as f:
                f.write(response.text)

            log("Successfully downloaded Kometa anime IDs")
            return True

        except (requests.RequestException, OSError) as e:
            log(f"Failed to download Kometa anime IDs: {e}")
            return False

    def _download_anime_lists(self) -> bool:
        """Download anime-lists XML from GitHub."""
        try:
            log("Downloading anime-lists XML...")
            response = requests.get(self.anime_lists_url, timeout=30)
            response.raise_for_status()

            with open(self.anime_lists_cache_file, "w", encoding="utf-8") as f:
                f.write(response.text)

            log("Successfully downloaded anime-lists XML")
            return True

        except (requests.RequestException, OSError) as e:
            log(f"Failed to download anime-lists XML: {e}")
            return False

    def _load_kometa_mappings(self) -> Dict:
        """Load Kometa anime IDs mapping from cache or download if needed."""
        if self._kometa_mappings:
            return self._kometa_mappings

        # Check cache validity
        if not self._is_cache_valid(self.kometa_cache_file):
            if not self._download_kometa_ids():
                log("Failed to download Kometa IDs, using existing cache if available")
                if not os.path.exists(self.kometa_cache_file):
                    log("No Kometa IDs cache available")
                    return {}

        # Load from cache
        try:
            with open(self.kometa_cache_file, "r", encoding="utf-8") as f:
                self._kometa_mappings = json.load(f)
            log(f"Loaded {len(self._kometa_mappings)} Kometa anime ID mappings")
            return self._kometa_mappings

        except (json.JSONDecodeError, OSError) as e:
            log(f"Failed to load Kometa IDs cache: {e}")
            self._kometa_mappings = {}
            return {}

    def _load_anime_lists_mappings(self) -> Dict:
        """Load anime-lists XML mapping from cache or download if needed."""
        if self._anime_lists_mappings:
            return self._anime_lists_mappings

        # Check cache validity
        if not self._is_cache_valid(self.anime_lists_cache_file):
            if not self._download_anime_lists():
                log("Failed to download anime-lists, using existing cache if available")
                if not os.path.exists(self.anime_lists_cache_file):
                    log("No anime-lists cache available")
                    return {}

        # Parse XML and build mapping
        try:
            tree = ET.parse(self.anime_lists_cache_file)
            root = tree.getroot()

            # Build mapping that can handle multiple AniDB IDs per TVDB ID
            self._anime_lists_mappings = {}

            for anime in root.findall("anime"):
                anidb_id = anime.get("anidbid")
                tvdb_id = anime.get("tvdbid")

                if anidb_id and tvdb_id and tvdb_id not in ["unknown", "hentai"]:
                    try:
                        tvdb_id_int = int(tvdb_id)
                        anidb_id_int = int(anidb_id)

                        # Support multiple AniDB IDs per TVDB ID (for multiple seasons)
                        if tvdb_id_int not in self._anime_lists_mappings:
                            self._anime_lists_mappings[tvdb_id_int] = []

                        if anidb_id_int not in self._anime_lists_mappings[tvdb_id_int]:
                            self._anime_lists_mappings[tvdb_id_int].append(anidb_id_int)

                    except ValueError:
                        continue

            log(f"Loaded {len(self._anime_lists_mappings)} anime-lists TVDB mappings")
            return self._anime_lists_mappings

        except (ET.ParseError, OSError) as e:
            log(f"Failed to load anime-lists cache: {e}")
            self._anime_lists_mappings = {}
            return {}

    def tvdb_to_anilist_ids(self, tvdb_id: int) -> List[int]:
        """Convert TVDB ID to AniList IDs using the mapping repositories.

        This handles the case where one TVDB ID maps to multiple AniDB IDs
        (representing different seasons), each potentially mapping to different AniList IDs.
        """
        try:
            # Load mappings
            kometa_mappings = self._load_kometa_mappings()
            anime_lists_mappings = self._load_anime_lists_mappings()

            # Step 1: Get AniDB IDs from TVDB ID using anime-lists
            anidb_ids = anime_lists_mappings.get(tvdb_id, [])
            if not anidb_ids:
                log(f"No AniDB IDs found for TVDB ID {tvdb_id}")
                return []

            # Step 2: Get AniList IDs from all AniDB IDs using Kometa mappings
            all_anilist_ids = []

            for anidb_id in anidb_ids:
                anidb_str = str(anidb_id)
                if anidb_str not in kometa_mappings:
                    log(
                        f"No Kometa mapping found for AniDB ID {anidb_id} (TVDB {tvdb_id})"
                    )
                    continue

                kometa_entry = kometa_mappings[anidb_str]
                anilist_id = kometa_entry.get("anilist_id")

                if not anilist_id:
                    log(f"No AniList ID found for AniDB ID {anidb_id} (TVDB {tvdb_id})")
                    continue

                # Handle multiple AniList IDs (comma-separated)
                if isinstance(anilist_id, str) and "," in anilist_id:
                    season_anilist_ids = [
                        int(id.strip()) for id in anilist_id.split(",")
                    ]
                elif isinstance(anilist_id, (int, str)):
                    season_anilist_ids = [int(anilist_id)]
                else:
                    log(f"Invalid AniList ID format: {anilist_id}")
                    continue

                all_anilist_ids.extend(season_anilist_ids)

            # Remove duplicates while preserving order
            unique_anilist_ids = []
            for anilist_id in all_anilist_ids:
                if anilist_id not in unique_anilist_ids:
                    unique_anilist_ids.append(anilist_id)

            if unique_anilist_ids:
                log(
                    f"Mapped TVDB {tvdb_id} -> AniDB {anidb_ids} -> AniList {unique_anilist_ids}"
                )
            else:
                log(f"No AniList mappings found for TVDB {tvdb_id}")

            return unique_anilist_ids

        except (KeyError, ValueError, TypeError) as e:
            log(f"Error mapping TVDB {tvdb_id} to AniList: {e}")
            return []

    def get_mapping_stats(self) -> Dict[str, int]:
        """Get statistics about the loaded mappings."""
        kometa_mappings = self._load_kometa_mappings()
        anime_lists_mappings = self._load_anime_lists_mappings()

        # Count how many entries have AniList IDs
        anilist_count = 0
        for entry in kometa_mappings.values():
            if entry.get("anilist_id"):
                anilist_count += 1

        return {
            "kometa_entries": len(kometa_mappings),
            "anime_lists_entries": len(anime_lists_mappings),
            "anilist_mappings": anilist_count,
        }

    def refresh_cache(self) -> bool:
        """Force refresh of all cached mappings."""
        log("Refreshing ID mapping cache...")

        # Clear in-memory cache
        self._kometa_mappings = {}
        self._anime_lists_mappings = {}

        # Download fresh data
        kometa_success = self._download_kometa_ids()
        anime_lists_success = self._download_anime_lists()

        if kometa_success and anime_lists_success:
            log("Successfully refreshed ID mapping cache")
            return True
        else:
            log("Failed to refresh some ID mapping data")
            return False


# Create the global instance
id_mapper = AnimeIDMapper()
