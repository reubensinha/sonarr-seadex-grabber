"""Client for interacting with Sonarr API to manage series."""

import requests
from config import SONARR_API_KEY, SONARR_URL, SONARR_SERIES_TYPE, SONARR_TAGS
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

        # Log filtering configuration
        filter_msg = []
        if SONARR_SERIES_TYPE:
            filter_msg.append(f"type={SONARR_SERIES_TYPE}")
        if SONARR_TAGS:
            filter_msg.append(f"tags={SONARR_TAGS}")
        
        if filter_msg:
            log(f"Filtering series by: {', '.join(filter_msg)}")

        series_list = []
        filtered_count = 0
        
        for series in response_list:
            if not series.get("monitored", False):
                continue
                
            # Filter by series type if configured
            if SONARR_SERIES_TYPE and series.get("seriesType", "").lower() != SONARR_SERIES_TYPE.lower():
                filtered_count += 1
                continue
                
            # Filter by tags if configured
            if SONARR_TAGS:
                series_tags = series.get("tags", [])
                if not any(tag in series_tags for tag in SONARR_TAGS):
                    filtered_count += 1
                    continue

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

        if filtered_count > 0:
            log(f"Filtered out {filtered_count} series based on configuration")
        
        log(f"Found {len(series_list)} monitored series matching criteria")
        return series_list
