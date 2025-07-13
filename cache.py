"""Functions for managing seen torrents and series data."""

import os
import json
from config import DATA_DIR
from data_class import Series

os.makedirs(DATA_DIR, exist_ok=True)


def load_json(filename, default=None) -> list[Series]:
    """Load JSON data from a file, returning default if file does not exist or is invalid."""
    if default is None:
        default = []
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return default


def save_json(filename, data):
    """Save JSON data to a file."""
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
