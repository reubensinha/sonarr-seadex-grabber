"""Miscellaneous utility functions."""

import datetime
import time
from datetime import timedelta


def log(message):
    """Log a message in console with a timestamp."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


class RateLimiter:
    """Rate limiter using token bucket algorithm for API rate limiting."""

    def __init__(self, max_requests=30, window_seconds=60):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum number of requests allowed in the time window
            window_seconds: Time window in seconds (default 60 for per-minute limiting)
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = []

    def wait_if_needed(self):
        """Wait if necessary to respect rate limits."""
        current_time = datetime.datetime.now()

        # Remove requests older than the window
        cutoff_time = current_time - timedelta(seconds=self.window_seconds)
        self.requests = [req_time for req_time in self.requests if req_time > cutoff_time]

        # If we're at the limit, wait until the oldest request expires
        if len(self.requests) >= self.max_requests:
            oldest_request = min(self.requests)
            wait_until = oldest_request + timedelta(seconds=self.window_seconds)
            if current_time < wait_until:
                wait_time = (wait_until - current_time).total_seconds()
                log(f"Rate limit reached, waiting {wait_time:.1f} seconds...")
                time.sleep(wait_time)
                # Clean up expired requests after waiting
                current_time = datetime.datetime.now()
                cutoff_time = current_time - timedelta(seconds=self.window_seconds)
                self.requests = [req_time for req_time in self.requests if req_time > cutoff_time]

        # Record this request
        self.requests.append(current_time)
