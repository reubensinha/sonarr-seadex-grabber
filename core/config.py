"""Configuration for Sonarr and external metadata services"""

import os
from pathlib import Path
import yaml

# config.yaml lives at the project root, one level up from this package
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_config():
    """Load configuration from config.yaml file, return empty dict if file doesn't exist or is malformed"""
    config_file = _PROJECT_ROOT / "config.yaml"

    if not config_file.exists():
        print(f"Warning: Configuration file not found: {config_file}. Using environment variables and defaults.")
        return {}

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        print(f"Warning: Error parsing configuration file: {e}. Using environment variables and defaults.")
        return {}
    except Exception as e:
        print(f"Warning: Error reading configuration file: {e}. Using environment variables and defaults.")
        return {}


def get_env_or_config(env_var, config_value, default=None):
    """Get value from environment variable first, then config file, then default"""
    env_value = os.getenv(env_var)
    if env_value is not None:
        return env_value
    return config_value if config_value is not None else default


def get_nested_config(config, keys, default=None):
    """Safely get nested configuration values"""
    try:
        result = config
        for key in keys:
            result = result.get(key, {})
        return result if result != {} else default
    except (AttributeError, TypeError):
        return default


# Load the configuration
_config = load_config()

# General settings
STARTUP_SCAN = get_env_or_config(
    "STARTUP_SCAN", get_nested_config(_config, ["general", "startup_scan"]), True
)

# Data directory for persistent cache
DATA_DIR = get_env_or_config("DATA_DIR", get_nested_config(_config, ["data", "dir"]), "data")
KNOWN_SERIES_FILE = get_env_or_config(
    "KNOWN_SERIES_FILE", get_nested_config(_config, ["data", "known_series_file"]), "known_series.json"
)
# Holds UI-adjustable runtime overrides (currently just sync_interval) -
# kept separate from config.yaml so the settings page never has to rewrite
# that hand-edited file (PyYAML's safe_load/safe_dump don't round-trip comments).
SETTINGS_FILE = get_env_or_config(
    "SETTINGS_FILE", get_nested_config(_config, ["data", "settings_file"]), "settings.json"
)

# Scheduling
# If the SYNC_INTERVAL *environment variable* specifically is set, the
# interval is pinned and the settings page can't change it - lets an
# operator enforce a fixed interval in a container/production deployment.
# config.yaml's value (or the hardcoded fallback below) is just an initial
# seed the user can freely adjust from the UI when no env var is present.
SYNC_INTERVAL_LOCKED = os.getenv("SYNC_INTERVAL") is not None

sync_interval_value = get_env_or_config("SYNC_INTERVAL", get_nested_config(_config, ["scheduling", "sync_interval"]), "86400")
try:
    if isinstance(sync_interval_value, (int, str)):
        SYNC_INTERVAL = int(sync_interval_value)
    else:
        SYNC_INTERVAL = 86400
except (ValueError, TypeError):
    SYNC_INTERVAL = 86400

# Sonarr (sensitive - prefer environment variables)
SONARR_URL = get_env_or_config("SONARR_URL", get_nested_config(_config, ["sonarr", "url"]))
SONARR_API_KEY = get_env_or_config("SONARR_API_KEY", get_nested_config(_config, ["sonarr", "api_key"]))
SONARR_SERIES_TYPE = get_env_or_config(
    "SONARR_SERIES_TYPE", get_nested_config(_config, ["sonarr", "series_type"]), ""
)

# Handle SONARR_TAGS as environment variable (comma-separated) or YAML list.
# Sonarr's API returns tag IDs as ints, so normalize both sources to list[int]
# to avoid a str/int mismatch that would silently break tag filtering.
env_tags = os.getenv("SONARR_TAGS")
if env_tags:
    raw_tags = [tag.strip() for tag in env_tags.split(",") if tag.strip()]
else:
    raw_tags = get_nested_config(_config, ["sonarr", "tags"]) or []

SONARR_TAGS = []
for _tag in raw_tags:
    try:
        SONARR_TAGS.append(int(_tag))
    except (ValueError, TypeError):
        print(f"Warning: ignoring non-numeric SONARR_TAGS entry: {_tag!r}")

# AniList
ANILIST_API_URL = get_env_or_config(
    "ANILIST_API_URL", get_nested_config(_config, ["anilist", "api_url"]), "https://graphql.anilist.co"
)

# Seadex
COLLECTIONS_URL = get_env_or_config(
    "COLLECTIONS_URL",
    get_nested_config(_config, ["seadex", "collections_url"]),
    "https://releases.moe/api/collections/entries/records",
)
TORRENT_URL = get_env_or_config(
    "TORRENT_URL",
    get_nested_config(_config, ["seadex", "torrent_url"]),
    "https://releases.moe/api/collections/torrents/records",
)

# Scoring
scoring_is_best_weight = get_env_or_config("SCORING_IS_BEST_WEIGHT", get_nested_config(_config, ["scoring", "is_best_weight"]), "2")
try:
    if isinstance(scoring_is_best_weight, (int, str)):
        SCORING_IS_BEST_WEIGHT = int(scoring_is_best_weight)
    else:
        SCORING_IS_BEST_WEIGHT = 2
except (ValueError, TypeError):
    SCORING_IS_BEST_WEIGHT = 2

scoring_dual_audio_weight = get_env_or_config("SCORING_DUAL_AUDIO_WEIGHT", get_nested_config(_config, ["scoring", "dual_audio_weight"]), "1")
try:
    if isinstance(scoring_dual_audio_weight, (int, str)):
        SCORING_DUAL_AUDIO_WEIGHT = int(scoring_dual_audio_weight)
    else:
        SCORING_DUAL_AUDIO_WEIGHT = 1
except (ValueError, TypeError):
    SCORING_DUAL_AUDIO_WEIGHT = 1

SCORING_TRACKER_WEIGHTS = get_nested_config(_config, ["scoring", "tracker_weights"]) or {
    "Nyaa": 0,
    "AB": -10,
    "default": 0
}

# qBittorrent (sensitive - prefer environment variables)
QB_URL = get_env_or_config("QB_URL", get_nested_config(_config, ["qbittorrent", "url"]))
QB_USER = get_env_or_config("QB_USER", get_nested_config(_config, ["qbittorrent", "username"]))
QB_PASS = get_env_or_config("QB_PASS", get_nested_config(_config, ["qbittorrent", "password"]))
QB_CATEGORY = get_env_or_config(
    "QB_CATEGORY", get_nested_config(_config, ["qbittorrent", "category"]), "anime-sonarr"
)

# Webhook Server (sensitive - prefer environment variables)
WEBHOOK_HOST = get_env_or_config(
    "WEBHOOK_HOST", get_nested_config(_config, ["webhook", "host"]), "localhost"
)

webhook_port = get_env_or_config("WEBHOOK_PORT", get_nested_config(_config, ["webhook", "port"]), "8765")
try:
    if isinstance(webhook_port, (int, str)):
        WEBHOOK_PORT = int(webhook_port)
    else:
        WEBHOOK_PORT = 8765
except (ValueError, TypeError):
    WEBHOOK_PORT = 8765

use_webhook = get_env_or_config("USE_WEBHOOK", get_nested_config(_config, ["webhook", "enabled"]), "false")
USE_WEBHOOK = str(use_webhook).lower() in ("true", "1", "yes", "on")
