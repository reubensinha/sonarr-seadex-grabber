"""Client for interacting with Sonarr API to manage series."""

import requests
from core.config import SONARR_API_KEY, SONARR_URL, SONARR_SERIES_TYPE, SONARR_TAGS
from core.data_class import Series
from core.utils import log

def get_headers():
    """Get headers for Sonarr API requests."""
    api_key = SONARR_API_KEY
    if api_key and isinstance(api_key, str):
        return {"X-Api-Key": api_key}
    return {"X-Api-Key": ""}


def _parse_series(raw: dict) -> Series | None:
    """Build a Series from a raw Sonarr /series API item. Returns None if it's missing an ID."""
    sonarr_id = raw.get("id")
    title = raw.get("title", "")

    if sonarr_id is None:
        log(f"Skipping series '{title}' - missing ID")
        return None

    # Extract number of seasons excluding specials (season 0)
    seasons = raw.get("seasons", [])
    num_seasons = len([season for season in seasons if season.get("seasonNumber", 0) > 0])

    return Series(
        sonarr_id=sonarr_id,
        title=title,
        num_seasons=num_seasons,
        tvdb_id=raw.get("tvdbId"),
        title_slug=raw.get("titleSlug"),
        anilist_entries=[],
    )


class SonarrClient:
    """Client for interacting with Sonarr API."""

    def get_monitored_series(self) -> list[Series] | None:
        """Get the list of monitored series from Sonarr. Returns None if there's an error."""
        url = f"{SONARR_URL}/api/v3/series"
        try:
            response = requests.get(url, headers=get_headers(), timeout=10)
            response.raise_for_status()
            response_list = response.json()
        except requests.RequestException as e:
            log(f"Error fetching series from Sonarr: {e}")
            return None

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
            if (
                SONARR_SERIES_TYPE
                and isinstance(SONARR_SERIES_TYPE, str)
                and series.get("seriesType", "").lower() != SONARR_SERIES_TYPE.lower()
            ):
                filtered_count += 1
                continue

            # Filter by tags if configured
            if SONARR_TAGS:
                series_tags = series.get("tags", [])
                if not any(tag in series_tags for tag in SONARR_TAGS):
                    filtered_count += 1
                    continue

            series_data = _parse_series(series)
            if series_data is None:
                continue

            series_list.append(series_data)

        if filtered_count > 0:
            log(f"Filtered out {filtered_count} series based on configuration")

        log(f"Found {len(series_list)} monitored series matching criteria")
        return series_list

    def get_series_by_id(self, sonarr_id: int) -> Series | None:
        """Fetch a single series from Sonarr by its ID. Returns None on error or if missing."""
        url = f"{SONARR_URL}/api/v3/series/{sonarr_id}"
        try:
            response = requests.get(url, headers=get_headers(), timeout=10)
            response.raise_for_status()
            raw = response.json()
        except requests.RequestException as e:
            log(f"Error fetching series {sonarr_id} from Sonarr: {e}")
            return None

        return _parse_series(raw)

    def get_series_history(self, sonarr_id: int, limit: int = 1) -> list[dict]:
        """Get the most recent import events for a series from Sonarr's history.

        Returns a list of {sourceTitle, date, quality} dicts, newest first.
        """
        url = f"{SONARR_URL}/api/v3/history/series"
        try:
            response = requests.get(
                url,
                params={"seriesId": sonarr_id, "eventType": 3},
                headers=get_headers(),
                timeout=10,
            )
            response.raise_for_status()
            records = response.json()
        except requests.RequestException as e:
            log(f"Error fetching history for series {sonarr_id} from Sonarr: {e}")
            return []

        records.sort(key=lambda r: r.get("date", ""), reverse=True)

        return [
            {
                "sourceTitle": r.get("sourceTitle"),
                "date": r.get("date"),
                "quality": (r.get("quality") or {}).get("quality", {}).get("name"),
            }
            for r in records[:limit]
        ]
