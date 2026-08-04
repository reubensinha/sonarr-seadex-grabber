"""Dashboard routes: main page plus small HTMX-polled status/log fragments."""

from fastapi import APIRouter, Request

from core import sync_manager
from core.cache import load_json
from core.config import KNOWN_SERIES_FILE, SONARR_URL
from core.data_class import Series
from core.utils import get_recent_logs
from webapp.app import templates

router = APIRouter()

_SORT_OPTIONS = {"updated", "title", "sonarr_id"}


def _sort_key(series: Series, sort: str):
    if sort == "title":
        return series.title.lower()
    if sort == "sonarr_id":
        return series.sonarr_id
    # "updated" (default): most recently updated on SeaDex across the
    # series' entries. Empty string sorts before any real timestamp, so
    # unmapped/stale series naturally end up last even with reverse=True.
    timestamps = [e.seadex_updated_at for e in series.anilist_entries if e.seadex_updated_at]
    return max(timestamps) if timestamps else ""


@router.get("/")
def dashboard(request: Request, sort: str = "updated"):
    if sort not in _SORT_OPTIONS:
        sort = "updated"

    known_series: list[Series] = load_json(KNOWN_SERIES_FILE, default=[])
    known_series.sort(key=lambda s: _sort_key(s, sort), reverse=(sort == "updated"))

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "series_list": known_series,
            "status": sync_manager.get_status(),
            "sync_interval": sync_manager.get_sync_interval(),
            "sonarr_url": SONARR_URL,
            "sort": sort,
        },
    )


@router.get("/partials/status")
def status_partial(request: Request):
    return templates.TemplateResponse(
        request, "partials/status.html", {"status": sync_manager.get_status()}
    )


@router.get("/partials/logs")
def logs_partial(request: Request):
    logs = list(reversed(get_recent_logs(150)))
    return templates.TemplateResponse(request, "partials/logs.html", {"logs": logs})
