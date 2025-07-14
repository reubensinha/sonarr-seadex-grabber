"""Client for interacting with Seadex API."""

from math import inf
import requests
from data_class import Trs
from utils import log
from config import COLLECTIONS_URL, TORRENT_URL


class SeadexClient:
    """Client for interacting with Seadex API."""

    def get_torrent_info(self, trs_id):
        """Get detailed torrent info for a given TRS ID."""
        try:
            response = requests.get(
                TORRENT_URL, params={"filter": f"(id='{trs_id}')"}, timeout=10
            )
            response.raise_for_status()
            items = response.json().get("items", [])
            return items[0] if items else None
        except requests.RequestException as e:
            log(f"Failed to fetch torrent info for TRS ID {trs_id}: {e}")
            return None

    def get_seadex_releases(self, anilist_id: int) -> list[Trs]:
        """Get Seadex releases for a given AniList ID."""
        try:
            response = requests.get(
                COLLECTIONS_URL, params={"filter": f"(alID={anilist_id})"}, timeout=10
            )
            response.raise_for_status()
            entries = response.json().get("items", [])
        except requests.RequestException as e:
            log(f"Failed to fetch Seadex entries for AniList ID {anilist_id}: {e}")
            return []

        if not entries:
            log(f"No Seadex collection entries found for AniList ID {anilist_id}")
            return []

        # Extract all TRS IDs from collection entries
        trs_ids = []
        for entry in entries:
            trs_list = entry.get("trs", [])
            trs_ids.extend(trs_list)

        if not trs_ids:
            log(f"No TRS IDs found in collection entries for AniList ID {anilist_id}")
            return []

        # Get detailed torrent info for each TRS ID and create Trs objects
        torrents = []
        for trs_id in trs_ids:
            torrent_info = self.get_torrent_info(trs_id)
            if torrent_info:
                # Extract required data with safe defaults
                info_hash: str = torrent_info.get("infoHash", "")
                tracker = torrent_info.get("tracker", "")
                url = torrent_info.get("url", "")
                is_best = torrent_info.get("isBest", False)
                dual_audio = torrent_info.get("dualAudio", False)

                # Skip if missing essential data
                if not info_hash or not url:
                    log(f"Skipping TRS {trs_id} - missing essential data")
                    continue
                
                # Check if this is a private tracker torrent with redacted info hash
                if info_hash == "<redacted>":
                    private = True
                    log(f"TRS {trs_id} is from private tracker - info hash redacted")
                else:
                    private = False

                # Create Trs object
                trs = Trs(
                    id=trs_id,
                    info_hash=info_hash,
                    tracker=tracker,
                    url=url,
                    is_best=is_best,
                    dual_audio=dual_audio,
                    chosen=False,
                    private=private
                )

                torrents.append(trs)
                private_msg = " (private)" if private else ""
                log(
                    f"Found torrent: {trs_id} ({'best' if is_best else 'normal'}, "
                    f"{'dual audio' if dual_audio else 'single audio'}){private_msg}"
                )
            else:
                log(f"Failed to get torrent info for TRS ID {trs_id}")

        log(f"Found {len(torrents)} valid torrents for AniList ID {anilist_id}")
        return torrents
