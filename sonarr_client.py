"""Client for interacting with Sonarr API to manage series."""

import requests
from config import SONARR_API_KEY, SONARR_URL
from data_class import Series
from utils import log

HEADERS = {"X-Api-Key": SONARR_API_KEY}


class SonarrClient:
    """Client for interacting with Sonarr API."""

    def get_monitored_series(self) -> list[Series]:
        """Get the list of monitored series from Sonarr."""
        url = f"{SONARR_URL}/api/v3/series"
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            response_list = response.json()
        except requests.RequestException as e:
            log(f"Error fetching series from Sonarr: {e}")
            return []

        if not response_list:
            log("No series found in Sonarr.")
            return []

        series_list = []
        for series in response_list:
            if series.get("monitored", False):
                sonarr_id = series.get("id")
                title = series.get("title", "")

                # Skip series without a valid ID
                if sonarr_id is None:
                    log(f"Skipping series '{title}' - missing ID")
                    continue

                # Extract number of seasons excluding specials (season 0)
                seasons = series.get("seasons", [])
                num_seasons = len(
                    [season for season in seasons if season.get("seasonNumber", 0) > 0]
                )

                series_data = Series(
                    sonarr_id=sonarr_id,
                    title=title,
                    num_seasons=num_seasons,
                    anilist_entries=[],
                )

                series_list.append(series_data)

        return series_list
