"""Coordinates concurrent access to sync jobs and known_series.json.

Three different triggers can ask for a sync to run: the scheduled background
loop, an incoming Sonarr webhook, and manual buttons in the WebUI. Without a
guard, two of these firing close together could run update_all_series
concurrently and tear the known_series.json write. SYNC_LOCK serializes sync
runs; DATA_LOCK serializes direct reads/writes of known_series.json made by
the WebUI's data-correction routes.
"""

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from .cache import load_json, save_json
from .config import (
    QB_CATEGORY,
    QB_CATEGORY_LOCKED,
    QB_PASS,
    QB_PASS_LOCKED,
    QB_URL,
    QB_URL_LOCKED,
    QB_USER,
    QB_USER_LOCKED,
    SETTINGS_FILE,
    SONARR_API_KEY,
    SONARR_API_KEY_LOCKED,
    SONARR_URL,
    SONARR_URL_LOCKED,
    SYNC_INTERVAL,
    SYNC_INTERVAL_LOCKED,
)
from .utils import log

# Serializes full/partial sync runs so at most one is ever in flight.
SYNC_LOCK = threading.Lock()

# Guards direct known_series.json read-modify-write cycles performed by the
# WebUI's data-correction routes (ignore toggle, torrent override, etc).
DATA_LOCK = threading.Lock()

# Guards against an accidental near-zero value hammering Seadex/AniList/
# Sonarr - only applies to a positive value, a deliberate 0 bypasses it.
_MIN_SYNC_INTERVAL_SECONDS = 300  # 5 minutes


def clamp_sync_interval_hours(hours: float) -> int:
    """Convert a Settings-page hours value to seconds. 0 (or negative) means
    "disabled" and passes through unclamped; any positive value is floored
    to _MIN_SYNC_INTERVAL_SECONDS."""
    if hours <= 0:
        return 0
    return max(int(hours * 3600), _MIN_SYNC_INTERVAL_SECONDS)


def get_sync_interval() -> int:
    """Return the current sync interval in seconds.

    If SYNC_INTERVAL_LOCKED (the env var was set), always returns the
    config-derived value, ignoring any override file - an operator-enforced
    interval can't be changed from the settings page. Otherwise returns the
    settings.json override if one has been set, else the config.yaml/default.
    """
    if SYNC_INTERVAL_LOCKED:
        return SYNC_INTERVAL

    overrides = load_json(SETTINGS_FILE, default={})
    return overrides.get("sync_interval", SYNC_INTERVAL)


def set_sync_interval(seconds: int) -> bool:
    """Persist a new sync interval override. Refuses (returns False, no
    write) if SYNC_INTERVAL_LOCKED."""
    if SYNC_INTERVAL_LOCKED:
        log("Refusing to change sync interval - locked via the SYNC_INTERVAL environment variable")
        return False

    with DATA_LOCK:
        overrides = load_json(SETTINGS_FILE, default={})
        overrides["sync_interval"] = seconds
        save_json(SETTINGS_FILE, overrides)
    log(f"Sync interval changed to {seconds} seconds")
    return True


def _get_runtime_value(settings_key: str, locked: bool, static_value):
    """Shared precedence for a single Settings-page-adjustable value: an
    env-var lock wins outright; otherwise a settings.json override if one
    has been set, else the config.yaml/default value. Mirrors
    get_sync_interval's precedence, generalized to any field."""
    if locked:
        return static_value
    overrides = load_json(SETTINGS_FILE, default={})
    return overrides.get(settings_key, static_value)


def _set_runtime_value(settings_key: str, locked: bool, value, label: str) -> bool:
    """Shared write path for a single Settings-page-adjustable value.
    Refuses (returns False, no write) if locked."""
    if locked:
        log(f"Refusing to change {label} - locked via environment variable")
        return False
    with DATA_LOCK:
        overrides = load_json(SETTINGS_FILE, default={})
        overrides[settings_key] = value
        save_json(SETTINGS_FILE, overrides)
    log(f"{label} changed")
    return True


def get_sonarr_url() -> str | None:
    return _get_runtime_value("sonarr_url", SONARR_URL_LOCKED, SONARR_URL)


def set_sonarr_url(value: str) -> bool:
    return _set_runtime_value("sonarr_url", SONARR_URL_LOCKED, value, "Sonarr URL")


def get_sonarr_api_key() -> str | None:
    return _get_runtime_value("sonarr_api_key", SONARR_API_KEY_LOCKED, SONARR_API_KEY)


def set_sonarr_api_key(value: str) -> bool:
    return _set_runtime_value("sonarr_api_key", SONARR_API_KEY_LOCKED, value, "Sonarr API key")


def get_qb_url() -> str | None:
    return _get_runtime_value("qb_url", QB_URL_LOCKED, QB_URL)


def set_qb_url(value: str) -> bool:
    return _set_runtime_value("qb_url", QB_URL_LOCKED, value, "qBittorrent URL")


def get_qb_user() -> str | None:
    return _get_runtime_value("qb_user", QB_USER_LOCKED, QB_USER)


def set_qb_user(value: str) -> bool:
    return _set_runtime_value("qb_user", QB_USER_LOCKED, value, "qBittorrent username")


def get_qb_pass() -> str | None:
    return _get_runtime_value("qb_pass", QB_PASS_LOCKED, QB_PASS)


def set_qb_pass(value: str) -> bool:
    return _set_runtime_value("qb_pass", QB_PASS_LOCKED, value, "qBittorrent password")


def get_qb_category() -> str | None:
    return _get_runtime_value("qb_category", QB_CATEGORY_LOCKED, QB_CATEGORY)


def set_qb_category(value: str) -> bool:
    return _set_runtime_value("qb_category", QB_CATEGORY_LOCKED, value, "qBittorrent category")


@dataclass
class SyncStatus:
    """Snapshot of the current/last sync state, for the dashboard to render."""

    in_progress: bool = False
    trigger_source: Optional[str] = None
    current_target: Optional[str] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    last_error: Optional[str] = None
    next_scheduled_at: Optional[float] = None


_status = SyncStatus()
_status_lock = threading.Lock()


def get_status() -> SyncStatus:
    """Return a snapshot copy of the current sync status."""
    with _status_lock:
        return SyncStatus(**vars(_status))


def set_next_scheduled_at(timestamp: Optional[float]) -> None:
    """Record when the next scheduled sync is expected to run."""
    with _status_lock:
        _status.next_scheduled_at = timestamp


def is_busy() -> bool:
    """Non-blocking check for whether a sync is currently running."""
    return get_status().in_progress


def _run_locked(trigger_source: str, target: Optional[str], job: Callable[[], None]) -> bool:
    """Run job() under SYNC_LOCK, updating status before/after. Returns False if busy."""
    if not SYNC_LOCK.acquire(blocking=False):
        log(
            f"Sync already in progress, skipping '{trigger_source}' trigger"
            + (f" for {target}" if target else "")
        )
        return False

    with _status_lock:
        _status.in_progress = True
        _status.trigger_source = trigger_source
        _status.current_target = target
        _status.started_at = time.time()
        _status.last_error = None

    try:
        job()
    except Exception as e:  # noqa: BLE001 - surface any failure to the dashboard
        log(f"Sync job ('{trigger_source}') failed: {e}")
        with _status_lock:
            _status.last_error = str(e)
    finally:
        with _status_lock:
            _status.in_progress = False
            _status.finished_at = time.time()
        SYNC_LOCK.release()

    return True


def run_full_sync(trigger_source: str, skip_qbittorrent: bool = False) -> bool:
    """Run a full sync across all known/Sonarr series. Returns False if a sync was already running."""
    # Imported lazily to avoid a circular import (main.py imports sync_manager).
    from main import update_all_series

    return _run_locked(
        trigger_source, None, lambda: update_all_series(skip_qbittorrent=skip_qbittorrent)
    )


def run_single_series_sync(sonarr_id: int, trigger_source: str = "manual") -> bool:
    """Run a sync for a single series. Returns False if a sync was already running."""
    from main import update_single_series

    return _run_locked(
        trigger_source, str(sonarr_id), lambda: update_single_series(sonarr_id)
    )


def run_research_series(sonarr_id: int, trigger_source: str = "manual") -> bool:
    """Re-search Seadex torrents for a single series' known AniList entries only.
    Returns False if a sync was already running."""
    from main import research_series_torrents

    return _run_locked(
        trigger_source, str(sonarr_id), lambda: research_series_torrents(sonarr_id)
    )
