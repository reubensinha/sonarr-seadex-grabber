"""Settings page: scheduler interval control + blacklist visibility/removal.

Kept as a separate page from the main dashboard - these are low-frequency,
config-ish actions that don't belong cluttering the per-series list.
"""

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from core import sync_manager
from core.cache import load_json, save_json
from core.config import (
    KNOWN_SERIES_FILE,
    QB_CATEGORY_LOCKED,
    QB_PASS_LOCKED,
    QB_URL_LOCKED,
    QB_USER_LOCKED,
    SONARR_API_KEY_LOCKED,
    SONARR_URL_LOCKED,
    SYNC_INTERVAL_LOCKED,
)
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
            "sonarr_url": sync_manager.get_sonarr_url() or "",
            "sonarr_url_locked": SONARR_URL_LOCKED,
            "sonarr_api_key_set": bool(sync_manager.get_sonarr_api_key()),
            "sonarr_api_key_locked": SONARR_API_KEY_LOCKED,
            "qb_url": sync_manager.get_qb_url() or "",
            "qb_url_locked": QB_URL_LOCKED,
            "qb_user": sync_manager.get_qb_user() or "",
            "qb_user_locked": QB_USER_LOCKED,
            "qb_pass_set": bool(sync_manager.get_qb_pass()),
            "qb_pass_locked": QB_PASS_LOCKED,
            "qb_category": sync_manager.get_qb_category() or "",
            "qb_category_locked": QB_CATEGORY_LOCKED,
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


@router.post("/settings/sonarr")
def update_sonarr_settings(sonarr_url: str = Form(""), sonarr_api_key: str = Form("")):
    sync_manager.set_sonarr_url(sonarr_url.strip().rstrip("/"))
    # "Leave blank to keep current" for the secret - an empty submission
    # means the user didn't intend to change it, not that they want to
    # clear it (the field is never pre-filled with the real value).
    if sonarr_api_key.strip():
        sync_manager.set_sonarr_api_key(sonarr_api_key.strip())
    return RedirectResponse("/settings", status_code=303)


@router.post("/settings/qbittorrent")
def update_qbittorrent_settings(
    qb_url: str = Form(""),
    qb_user: str = Form(""),
    qb_pass: str = Form(""),
    qb_category: str = Form(""),
):
    sync_manager.set_qb_url(qb_url.strip().rstrip("/"))
    sync_manager.set_qb_user(qb_user.strip())
    if qb_pass.strip():
        sync_manager.set_qb_pass(qb_pass.strip())
    sync_manager.set_qb_category(qb_category.strip())
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
