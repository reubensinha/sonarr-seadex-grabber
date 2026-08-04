"""FastAPI application: dashboard/WebUI + Sonarr webhook, on one server.

Replaces the old standalone http.server-based webhook_server.py. Running
both the UI and the webhook on a single server means the app is always
reachable (health check, dashboard) regardless of whether USE_WEBHOOK is
enabled - only the /webhook route's behavior depends on that flag.
"""

import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

_WEBAPP_DIR = Path(__file__).parent

templates = Jinja2Templates(directory=str(_WEBAPP_DIR / "templates"))


def _fmt_time(ts):
    """Format a unix timestamp for display, or an em-dash if unset."""
    if not ts:
        return "—"
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _fmt_eta(ts):
    """Format a future unix timestamp as a rough countdown, or an em-dash if unset."""
    if not ts:
        return "—"
    remaining = ts - datetime.datetime.now().timestamp()
    if remaining <= 0:
        return "any moment now"
    minutes, seconds = divmod(int(remaining), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"in {hours}h {minutes}m"
    if minutes:
        return f"in {minutes}m {seconds}s"
    return f"in {seconds}s"


templates.env.filters["fmt_time"] = _fmt_time
templates.env.filters["fmt_eta"] = _fmt_eta

app = FastAPI(title="Seadex Sonarr Grabber")
app.mount(
    "/static", StaticFiles(directory=str(_WEBAPP_DIR / "static")), name="static"
)

# Imported after `app`/`templates` exist, since these route modules import
# them back (`from webapp.app import templates`).
from main import score_torrent, get_scoring_breakdown  # noqa: E402
from webapp.routes_dashboard import router as dashboard_router  # noqa: E402
from webapp.routes_actions import router as actions_router  # noqa: E402
from webapp.routes_webhook import router as webhook_router  # noqa: E402
from webapp.routes_settings import router as settings_router  # noqa: E402


def _group_by_release(torrents):
    """Group torrents by release_group for the SeaDex-style release-block
    layout. Not Jinja's builtin `groupby` - that sorts by the attribute
    first, and release_group can be None (crashes sorting against str in
    Python 3), so this groups in first-appearance order instead.

    Best/DualAudio/Alt are computed once per group (not per tracker
    posting), matching SeaDex's own UI - a release group is either the
    curated "Best" pick or an "Alt", and that status is uniform across its
    tracker postings in practice.
    """
    groups: dict[str, dict] = {}
    for t in torrents:
        name = t.release_group or "Unknown release group"
        group = groups.setdefault(
            name, {"name": name, "has_best": False, "has_dual_audio": False, "releases": []}
        )
        group["has_best"] = group["has_best"] or t.is_best
        group["has_dual_audio"] = group["has_dual_audio"] or t.dual_audio
        group["releases"].append(t)

    result = list(groups.values())
    for group in result:
        group["is_alt"] = not group["has_best"]
        group["releases"].sort(key=score_torrent, reverse=True)
        group["release_items"] = _sub_group_by_grouped_url(group["releases"])
    return result


def _sub_group_by_grouped_url(releases):
    """Bucket a release-group's torrents into standalone items or combined
    multi-part items, per SeaDex's groupedUrl (see Trs.grouped_url) - some
    release groups aren't one torrent but a set of per-episode torrents that
    only add up to the complete release together (e.g. Erai-raws), and
    should act as a single entry in the UI rather than one row each.

    Returns a list of {torrents, total_count, chosen_count, grouped_url}
    dicts, preserving the score-descending order the caller already sorted
    `releases` into.
    """
    buckets: dict[str, list] = {}
    order: list[str] = []
    for t in releases:
        # Torrents with no grouped_url are each their own standalone bucket.
        key = t.grouped_url or f"_standalone_{t.id}"
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(t)

    return [
        {
            "torrents": buckets[key],
            "total_count": len(buckets[key]),
            "chosen_count": sum(1 for t in buckets[key] if t.chosen),
            "grouped_url": buckets[key][0].grouped_url,
        }
        for key in order
    ]


templates.env.filters["score"] = score_torrent
templates.env.filters["breakdown"] = get_scoring_breakdown
templates.env.filters["group_by_release"] = _group_by_release

app.include_router(dashboard_router)
app.include_router(actions_router)
app.include_router(webhook_router)
app.include_router(settings_router)
