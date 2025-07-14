"""Functions for managing seen torrents and series data."""

import os
import json
from typing import Union, Any
from config import DATA_DIR
from data_class import Series

os.makedirs(DATA_DIR, exist_ok=True)


def load_json(filename, default=None) -> Union[list[Series], Any]:
    """Load JSON data from a file, returning default if file does not exist or is invalid."""
    if default is None:
        default = []
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            # Convert dictionaries back to Series objects if the data contains series
            # Check if it's a list of dictionaries with series-like structure
            if (
                isinstance(data, list)
                and len(data) > 0
                and isinstance(data[0], dict)
                and "sonarr_id" in data[0]
            ):
                return [Series.from_dict(item) for item in data]
            return data
        except json.JSONDecodeError:
            return default


def save_json(filename, data):
    """Save JSON data to a file."""
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        # Convert Series objects to dictionaries for JSON serialization
        if isinstance(data, list) and len(data) > 0 and hasattr(data[0], "to_dict"):
            serialized_data = [item.to_dict() for item in data]
            json.dump(serialized_data, f, indent=2)
        else:
            json.dump(data, f, indent=2)
