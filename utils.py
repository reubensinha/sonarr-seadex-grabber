"""Miscellaneous utility functions."""

import datetime


def log(message):
    """Log a message in console with a timestamp."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")
