"""Settings page: scheduler interval control + blacklist visibility/removal.

Kept as a separate page from the main dashboard - these are low-frequency,
config-ish actions that don't belong cluttering the per-series list.
"""

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from core import sync_manager
from core.cache import load_json, save_json
from core.config import KNOWN_SERIES_FILE, SYNC_INTERVAL_LOCKED
from core.data_class import Series
from core.utils import log
from webapp.app import templates

router = APIRouter()


@router.get("/settings")
def settings_page(request: Request):
    known_series: list[Series] = load_json(KNOWN_SERIES_FILE, default=[])
    blacklisted = [
        {"sonarr_id": s.sonarr_id, "series_title": s.title, "anilist_id": aid}
        for s in known_series
        for aid in s.blacklisted_anilist_ids
    ]

    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "sync_interval": sync_manager.get_sync_interval(),
            "sync_interval_locked": SYNC_INTERVAL_LOCKED,
            "blacklisted": blacklisted,
        },
    )


@router.post("/settings/sync-interval")
def update_sync_interval(hours: float = Form(...)):
    if SYNC_INTERVAL_LOCKED:
        log("Ignoring sync interval change request - locked via the SYNC_INTERVAL environment variable")
        return RedirectResponse("/settings", status_code=303)

    seconds = sync_manager.clamp_sync_interval_hours(hours)
    sync_manager.set_sync_interval(seconds)
    return RedirectResponse("/settings", status_code=303)


@router.post("/settings/blacklist/{sonarr_id}/{anilist_id}/remove")
def remove_from_blacklist(sonarr_id: int, anilist_id: int):
    if sync_manager.is_busy():
        log(f"Un-blacklist request for AniList ID {anilist_id} rejected - sync in progress")
        return RedirectResponse("/settings", status_code=303)

    with sync_manager.DATA_LOCK:
        known_series: list[Series] = load_json(KNOWN_SERIES_FILE, default=[])
        series = next((s for s in known_series if s.sonarr_id == sonarr_id), None)
        if series is not None and anilist_id in series.blacklisted_anilist_ids:
            series.blacklisted_anilist_ids.remove(anilist_id)
            log(f"Un-blacklisted AniList ID {anilist_id} from '{series.title}'")
            save_json(KNOWN_SERIES_FILE, known_series)

    return RedirectResponse("/settings", status_code=303)
