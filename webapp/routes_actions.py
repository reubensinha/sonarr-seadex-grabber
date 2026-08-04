"""Manual sync triggers and data-correction routes (replaces hand-editing
known_series.json).

DATA_LOCK is only ever held around the in-memory load/save of
known_series.json - never across a network call (qBittorrent submit, AniList
lookup) - so it stays a fast, short-held lock as intended by sync_manager.
Routes that mutate state check sync_manager.is_busy() first and simply
decline (with a flash-style message) while a sync is running, rather than
attempting fine-grained merge logic against an in-flight sync.
"""

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from clients.anilist_client import AniListClient
from clients.sonarr_client import SonarrClient
from core import sync_manager
from core.cache import load_json, save_json
from core.config import KNOWN_SERIES_FILE
from core.data_class import AniListSeries, Series
from core.utils import log
from main import (
    apply_chosen_torrents,
    group_siblings,
    mark_torrents_downloaded,
    merge_anilist_ids,
    set_preferred_torrents,
)
from webapp.app import templates

router = APIRouter()


def _find_entry(known_series: list[Series], anilist_id: int) -> tuple[Series | None, AniListSeries | None]:
    for series in known_series:
        for entry in series.anilist_entries:
            if entry.anilist_id == anilist_id:
                return series, entry
    return None, None


def _find_series(known_series: list[Series], sonarr_id: int) -> Series | None:
    return next((s for s in known_series if s.sonarr_id == sonarr_id), None)


@router.post("/sync")
def trigger_full_sync():
    if not sync_manager.run_full_sync(trigger_source="manual"):
        log("Manual full sync request ignored - a sync is already in progress")
    return RedirectResponse("/", status_code=303)


@router.post("/series/{sonarr_id}/sync")
def trigger_series_sync(sonarr_id: int):
    if not sync_manager.run_single_series_sync(sonarr_id, trigger_source="manual"):
        log(f"Manual resync for series {sonarr_id} ignored - a sync is already in progress")
    return RedirectResponse("/", status_code=303)


@router.post("/series/{sonarr_id}/research")
def trigger_series_research(sonarr_id: int):
    if not sync_manager.run_research_series(sonarr_id, trigger_source="manual"):
        log(f"Manual re-search for series {sonarr_id} ignored - a sync is already in progress")
    return RedirectResponse("/", status_code=303)


@router.post("/entries/{anilist_id}/ignore")
def toggle_ignore(anilist_id: int):
    if sync_manager.is_busy():
        log(f"Ignore toggle for AniList ID {anilist_id} rejected - sync in progress")
        return RedirectResponse("/", status_code=303)

    with sync_manager.DATA_LOCK:
        known_series: list[Series] = load_json(KNOWN_SERIES_FILE, default=[])
        _, entry = _find_entry(known_series, anilist_id)
        if entry is not None:
            entry.ignore = not entry.ignore
            log(f"AniList entry {anilist_id} ignore set to {entry.ignore}")
            save_json(KNOWN_SERIES_FILE, known_series)

    return RedirectResponse("/", status_code=303)


@router.post("/entries/{anilist_id}/download")
def download_torrent(anilist_id: int, torrent_id: str = Form(...)):
    if sync_manager.is_busy():
        log(f"Manual download for AniList ID {anilist_id} rejected - sync in progress")
        return RedirectResponse("/", status_code=303)

    # Unlocked read + qBittorrent submit (network I/O), then a locked save -
    # mirrors update_single_series's read/act/save pattern.
    known_series: list[Series] = load_json(KNOWN_SERIES_FILE, default=[])
    _, entry = _find_entry(known_series, anilist_id)
    if entry is not None:
        torrent = next((t for t in entry.torrents if t.id == torrent_id), None)
        if torrent is not None:
            # A multi-part release (Trs.grouped_url) is downloaded as a
            # whole - expand to every current part of it.
            apply_chosen_torrents(entry, group_siblings(entry, torrent))
            with sync_manager.DATA_LOCK:
                save_json(KNOWN_SERIES_FILE, known_series)

    return RedirectResponse("/", status_code=303)


@router.post("/entries/{anilist_id}/prefer")
def prefer_torrent(anilist_id: int, torrent_id: str = Form(...)):
    if sync_manager.is_busy():
        log(f"Manual preference for AniList ID {anilist_id} rejected - sync in progress")
        return RedirectResponse("/", status_code=303)

    # Pure in-memory, no network call - fits entirely inside DATA_LOCK.
    with sync_manager.DATA_LOCK:
        known_series: list[Series] = load_json(KNOWN_SERIES_FILE, default=[])
        _, entry = _find_entry(known_series, anilist_id)
        if entry is not None:
            torrent = next((t for t in entry.torrents if t.id == torrent_id), None)
            if torrent is not None and set_preferred_torrents(
                entry, group_siblings(entry, torrent)
            ):
                save_json(KNOWN_SERIES_FILE, known_series)

    return RedirectResponse("/", status_code=303)


@router.post("/entries/{anilist_id}/mark-downloaded")
def mark_downloaded(anilist_id: int, torrent_id: str = Form(...)):
    if sync_manager.is_busy():
        log(f"Mark-as-downloaded for AniList ID {anilist_id} rejected - sync in progress")
        return RedirectResponse("/", status_code=303)

    # Pure in-memory, no network call - fits entirely inside DATA_LOCK.
    with sync_manager.DATA_LOCK:
        known_series: list[Series] = load_json(KNOWN_SERIES_FILE, default=[])
        _, entry = _find_entry(known_series, anilist_id)
        if entry is not None:
            torrent = next((t for t in entry.torrents if t.id == torrent_id), None)
            if torrent is not None:
                mark_torrents_downloaded(entry, group_siblings(entry, torrent))
                save_json(KNOWN_SERIES_FILE, known_series)

    return RedirectResponse("/", status_code=303)


@router.post("/entries/{anilist_id}/remove")
def remove_entry(anilist_id: int):
    if sync_manager.is_busy():
        log(f"Remove request for AniList ID {anilist_id} rejected - sync in progress")
        return RedirectResponse("/", status_code=303)

    # Pure in-memory, no network call - fits entirely inside DATA_LOCK.
    with sync_manager.DATA_LOCK:
        known_series: list[Series] = load_json(KNOWN_SERIES_FILE, default=[])
        series, entry = _find_entry(known_series, anilist_id)
        if series is not None and entry is not None:
            series.anilist_entries = [
                e for e in series.anilist_entries if e.anilist_id != anilist_id
            ]
            if anilist_id not in series.blacklisted_anilist_ids:
                series.blacklisted_anilist_ids.append(anilist_id)
            log(
                f"Removed AniList entry {anilist_id} ({entry.title}) from "
                f"'{series.title}' and blacklisted it from future matching"
            )
            save_json(KNOWN_SERIES_FILE, known_series)

    return RedirectResponse("/", status_code=303)


@router.post("/series/{sonarr_id}/mapping")
def add_manual_mapping(sonarr_id: int, anilist_id: int = Form(...)):
    if sync_manager.is_busy():
        log(f"Manual AniList mapping for series {sonarr_id} rejected - sync in progress")
        return RedirectResponse("/", status_code=303)

    anilist = AniListClient()
    found = anilist.get_series_by_anilist_ids([anilist_id])
    if not found:
        log(f"Manual AniList mapping failed - AniList ID {anilist_id} not found")
        return RedirectResponse("/", status_code=303)

    found[0].manually_added = True

    known_series: list[Series] = load_json(KNOWN_SERIES_FILE, default=[])
    target = next((s for s in known_series if s.sonarr_id == sonarr_id), None)
    if target is not None:
        target.anilist_entries = merge_anilist_ids(target.anilist_entries, found)
        with sync_manager.DATA_LOCK:
            save_json(KNOWN_SERIES_FILE, known_series)

    return RedirectResponse("/", status_code=303)


@router.get("/series/{sonarr_id}/mapping/search")
def search_mapping_candidates(request: Request, sonarr_id: int, q: str = ""):
    """Live AniList title search backing the manual-mapping search box.

    Reuses AniListClient.search_anilist as-is - no new AniList API code.
    """
    results = []
    if q.strip():
        results = AniListClient().search_anilist(q.strip())

    return templates.TemplateResponse(
        request,
        "partials/mapping_results.html",
        {"sonarr_id": sonarr_id, "query": q, "results": results},
    )


@router.get("/series/{sonarr_id}/sonarr-history")
def sonarr_history(request: Request, sonarr_id: int):
    """Lazy-loaded 'last downloaded in Sonarr' fragment for a series card."""
    history = SonarrClient().get_series_history(sonarr_id, limit=1)
    last = history[0] if history else None

    return templates.TemplateResponse(
        request, "partials/sonarr_history.html", {"last": last}
    )
