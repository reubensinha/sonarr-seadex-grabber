"""Client for interacting with AniList API"""

import time

import requests

from config import ANILIST_API_URL
from data_class import AniListSeries
from utils import log, RateLimiter


class AniListClient:
    """Client for interacting with AniList API with rate limiting and retry logic."""

    def __init__(self):
        self.rate_limiter = RateLimiter(max_requests=30, window_seconds=60)

    def _make_request_with_retry(self, query, variables, max_retries=3):
        """Make a request to AniList API with rate limiting and retry logic."""
        for attempt in range(max_retries + 1):
            try:
                # Wait if we need to respect rate limits
                self.rate_limiter.wait_if_needed()

                response = requests.post(
                    ANILIST_API_URL,
                    json={"query": query, "variables": variables},
                    timeout=10,
                )

                # Handle rate limiting (429 Too Many Requests)
                if response.status_code == 429:
                    if attempt < max_retries:
                        # Get retry-after header or use exponential backoff
                        retry_after = response.headers.get("Retry-After")
                        if retry_after:
                            wait_time = int(retry_after)
                        else:
                            wait_time = (
                                2**attempt
                            ) * 60  # Exponential backoff: 1min, 2min, 4min

                        log(
                            f"Rate limited (429), waiting {wait_time} seconds before retry {attempt + 1}/{max_retries}"
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        log("Max retries reached for rate limiting, giving up")
                        return None

                response.raise_for_status()
                return response.json()

            except requests.RequestException as e:
                if attempt < max_retries:
                    wait_time = (2**attempt) * 5  # Exponential backoff: 5s, 10s, 20s
                    log(
                        f"Request failed: {e}, retrying in {wait_time} seconds (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait_time)
                else:
                    log(f"Max retries reached, final error: {e}")
                    return None

        return None

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

        # Use the retry mechanism
        response_data = self._make_request_with_retry(query, variables)
        if not response_data:
            log(f"Failed to get response from AniList for '{title}' after retries")
            return []

        results = response_data.get("data", {}).get("Page", {}).get("media", [])

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
