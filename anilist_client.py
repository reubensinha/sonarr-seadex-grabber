"""Client for interacting with AniList API"""

import requests
from config import ANILIST_API_URL
from data_class import AniListSeries
from utils import log


class AniListClient:
    """Client for interacting with AniList API."""

    def search_anilist(self, title) -> list[AniListSeries]:
        """
        Search AniList for a series by title and return the list of series. 
        Each season of the series may be a serparate entry.
        """

        query = """
        query ($search: String) {
        Page(perPage: 10) {
            media(search: $search, type: ANIME) {
            id
            title {
                romaji
                english
                native
            }
            format
            episodes
            seasonYear
            }
        }
        }
        """
        variables = {"search": title}

        try:
            response = requests.post(
                ANILIST_API_URL,
                json={"query": query, "variables": variables},
                timeout=10,
            )
            response.raise_for_status()
            results = response.json().get("data", {}).get("Page", {}).get("media", [])
        except requests.RequestException as e:
            log(f"AniList search error for '{title}': {e}")
            return []

        if not results:
            log(f"No AniList results found for '{title}'")
            return []

        anilist_series = []
        for item in results:
            # Extract relevant data with safe defaults
            anilist_id = item.get("id")
            title_obj = item.get("title", {})
            season_year = item.get("seasonYear")
            format_type = item.get("format", "")

            # Skip if missing essential data
            if not anilist_id or not season_year:
                continue

            # Filter out non-TV series formats to reduce irrelevant results
            # Focus on TV series and TV shorts, exclude movies, music videos, etc.
            if format_type not in ["TV", "TV_SHORT", "ONA", "OVA"]:
                continue

            # Get the best available title (prefer English, then Romaji, then Native)
            title = (
                title_obj.get("english")
                or title_obj.get("romaji")
                or title_obj.get("native")
                or "Unknown Title"
            )

            # Create AniListSeries object
            anilist_entry = AniListSeries(
                anilist_id=anilist_id,
                title=title,
                season_year=season_year,
                torrents=[],
                manually_added=False,
                ignore=False,
            )

            anilist_series.append(anilist_entry)
            log(f"Found AniList entry: {title} (ID: {anilist_id}, Year: {season_year})")

        # Sort by season year to get chronological order
        anilist_series.sort(key=lambda x: x.season_year)

        return anilist_series
