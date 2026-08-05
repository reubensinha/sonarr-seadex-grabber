"""Main script for Seaex Sonarr Monitor."""

import threading
import time

from clients.anilist_client import AniListClient
from clients.qbittorrent_client import send_to_qbittorrent
from clients.seadex_client import SeadexClient
from clients.sonarr_client import SonarrClient
from core import sync_manager
from core.cache import load_json, save_json
from core.config import (
    KNOWN_SERIES_FILE,
    SCORING_DUAL_AUDIO_WEIGHT,
    SCORING_IS_BEST_WEIGHT,
    SCORING_TRACKER_WEIGHTS,
    STARTUP_SCAN,
    USE_WEBHOOK,
    WEBHOOK_HOST,
    WEBHOOK_PORT,
)
from core.data_class import AniListSeries, Series, Trs
from core.utils import log


def migrate_series_data(series_list: list[Series]) -> list[Series]:
    """
    Migrate series data to handle backward compatibility.
    This function handles cases where old data might be missing fields.
    """
    migrated_count = 0

    for series in series_list:
        # Check if TVDB ID is missing (backward compatibility)
        if series.tvdb_id is None:
            # We can't populate TVDB ID without Sonarr data, but we can log it
            log(
                f"Series '{series.title}' (ID: {series.sonarr_id}) missing TVDB ID - "
                "will be populated from Sonarr during sync"
            )
            migrated_count += 1

    if migrated_count > 0:
        log(f"Found {migrated_count} series that need TVDB ID migration")

    return series_list

def sync_sonarr_series(
    known_series: list[Series], sonarr_series: list[Series]
) -> list[Series]:
    """Sync Known series with Sonarr series, adding or removing as necessary.

    Args:
        known_series: List of currently known series
        sonarr_series: List of series from Sonarr (should not be None)

    Returns:
        Updated list of series
    """
    # Create dictionaries for easier lookup by sonarr_id
    known_series_dict = {series.sonarr_id: series for series in known_series}
    sonarr_series_dict = {series.sonarr_id: series for series in sonarr_series}

    # Start with existing known series that are still in Sonarr
    synced_series = []

    # 1. Keep existing series that are still monitored in Sonarr
    for sonarr_id, known_series_item in known_series_dict.items():
        if sonarr_id in sonarr_series_dict:
            # Migration: Update TVDB ID if it's missing from old data
            sonarr_series_item = sonarr_series_dict[sonarr_id]
            if known_series_item.tvdb_id is None and sonarr_series_item.tvdb_id is not None:
                known_series_item.tvdb_id = sonarr_series_item.tvdb_id
                log(f"Migrated TVDB ID {sonarr_series_item.tvdb_id} for existing series: {known_series_item.title}")

            synced_series.append(known_series_item)
            log(f"Keeping existing series: {known_series_item.title}")

    # 2. Add new series that are in Sonarr but not in known_series
    for sonarr_id, sonarr_series_item in sonarr_series_dict.items():
        if sonarr_id not in known_series_dict:
            synced_series.append(sonarr_series_item)
            log(f"Added new series: {sonarr_series_item.title}")

    # 3. Log removed series (those in known_series but not in sonarr_series)
    for sonarr_id, known_series_item in known_series_dict.items():
        if sonarr_id not in sonarr_series_dict:
            log(f"Removed series (no longer monitored): {known_series_item.title}")

    return synced_series


def merge_anilist_ids(
    known_entries: list[AniListSeries], found_entries: list[AniListSeries]
) -> list[AniListSeries]:
    """Merge AniList IDs from found_entries into known_entries."""
    # Create dictionaries for easier lookup by anilist_id
    known_entries_dict = {entry.anilist_id: entry for entry in known_entries}
    found_entries_dict = {entry.anilist_id: entry for entry in found_entries}

    merged_entries = []

    # 1. Keep existing entries that are still found (don't modify them)
    for anilist_id, known_entry in known_entries_dict.items():
        if anilist_id in found_entries_dict:
            merged_entries.append(known_entry)
            log(
                f"Keeping existing AniList entry: {known_entry.title} (ID: {anilist_id})"
            )
        elif known_entry.manually_added or known_entry.ignore:
            # Keep manually added or ignored entries even if not found in search
            merged_entries.append(known_entry)
            log(
                f"Keeping manually added/ignored entry: {known_entry.title} (ID: {anilist_id})"
            )
        else:
            # Remove entries that are no longer found and not manually added/ignored
            log(
                f"Removing AniList entry: {known_entry.title} (ID: {anilist_id}) - no longer found in search"
            )

    # 2. Add new entries that are in found_entries but not in known_entries
    for anilist_id, found_entry in found_entries_dict.items():
        if anilist_id not in known_entries_dict:
            merged_entries.append(found_entry)
            log(f"Added new AniList entry: {found_entry.title} (ID: {anilist_id})")

    # Sort by season year for consistency
    merged_entries.sort(key=lambda x: x.season_year)

    return merged_entries


def score_torrent(torrent: Trs) -> int:
    """Score a torrent based on configurable weights for is_best, dual_audio, and tracker."""
    score = 0

    # Apply configurable weights
    if torrent.is_best:
        score += SCORING_IS_BEST_WEIGHT
    if torrent.dual_audio:
        score += SCORING_DUAL_AUDIO_WEIGHT

    # Apply tracker-specific scoring
    tracker_score = SCORING_TRACKER_WEIGHTS.get(
        torrent.tracker, SCORING_TRACKER_WEIGHTS.get("default", 0)
    )
    score += tracker_score

    # Note: Private torrents are included in scoring but handled differently in download
    return score


def get_scoring_breakdown(torrent: Trs) -> str:
    """Get detailed scoring breakdown for logging purposes."""
    breakdown = []

    if torrent.is_best:
        breakdown.append(f"is_best: +{SCORING_IS_BEST_WEIGHT}")
    if torrent.dual_audio:
        breakdown.append(f"dual_audio: +{SCORING_DUAL_AUDIO_WEIGHT}")

    tracker_score = SCORING_TRACKER_WEIGHTS.get(
        torrent.tracker, SCORING_TRACKER_WEIGHTS.get("default", 0)
    )
    if tracker_score != 0:
        breakdown.append(
            f"tracker({torrent.tracker}): {'+' if tracker_score >= 0 else ''}{tracker_score}"
        )

    if torrent.private:
        breakdown.append("private")

    return " | ".join(breakdown) if breakdown else "no bonuses"


def _siblings_of(torrents: list[Trs], target: Trs) -> list[Trs]:
    """Every torrent in `torrents` belonging to the same multi-part release as
    `target` (sharing its non-empty grouped_url), including target itself.
    Just [target] if it isn't part of a multi-part release."""
    if not target.grouped_url:
        return [target]
    return [t for t in torrents if t.grouped_url == target.grouped_url]


def group_siblings(anilist_entry: AniListSeries, torrent: Trs) -> list[Trs]:
    """Every torrent in this AniList entry that belongs to the same
    multi-part SeaDex release as `torrent` (see Trs.grouped_url), including
    itself. Acting on any one member of a multi-part release (Prefer,
    Download) should act on all of them - SeaDex represents things like
    per-episode releases as several independent torrent records that only
    add up to the complete release together.
    """
    return _siblings_of(anilist_entry.torrents, torrent)


def choose_best_and_merge_torrents(
    known_torrents: list[Trs], found_torrents: list[Trs]
) -> tuple[list[Trs], list[Trs]]:
    """Choose the best release from found_torrents and merge with known_torrents.

    Returns (pending, merged_torrents). `pending` is the list of torrents
    that should be submitted to qBittorrent - empty if nothing new needs to
    be sent (no candidates exist, or the current best release, including
    every part of a multi-part one, is already fully chosen). When the best
    candidate belongs to a multi-part release (Trs.grouped_url), `pending`
    only contains the parts not already chosen, so a new part appearing
    later (e.g. next week's episode) doesn't re-submit already-downloaded
    ones. This function never sets `chosen` itself - the caller must only
    set it after confirming a torrent was actually sent successfully, so a
    population-only pass (skip_qbittorrent=True) can never mark a torrent as
    chosen without having sent it.
    """
    # Create dictionaries for easier lookup by torrent id
    known_torrents_dict = {torrent.id: torrent for torrent in known_torrents}
    found_torrents_dict = {torrent.id: torrent for torrent in found_torrents}

    merged_torrents = []

    # 1. Keep existing torrents that are still found or are marked as chosen
    # or preferred. Do NOT touch `chosen` here - it must only change once we
    # know whether a different torrent has actually won and been sent.
    for torrent_id, known_torrent in known_torrents_dict.items():
        if torrent_id in found_torrents_dict:
            # Still on Seadex - refresh the fields Seadex controls and clear
            # any prior "removed" flag (self-healing if it reappeared).
            fresh = found_torrents_dict[torrent_id]
            known_torrent.is_best = fresh.is_best
            known_torrent.dual_audio = fresh.dual_audio
            known_torrent.private = fresh.private
            known_torrent.published_at = fresh.published_at
            known_torrent.release_group = fresh.release_group
            known_torrent.grouped_url = fresh.grouped_url
            if known_torrent.removed_from_seadex:
                log(f"Torrent {torrent_id} reappeared on Seadex - no longer marked removed")
                known_torrent.removed_from_seadex = False
            merged_torrents.append(known_torrent)
        elif known_torrent.chosen or known_torrent.preferred:
            # No longer on Seadex, but the user/app cares about it - keep it
            # visible, marked removed, stripped of the status Seadex no
            # longer vouches for.
            if not known_torrent.removed_from_seadex:
                log(
                    f"Torrent {torrent_id} no longer found on Seadex - marking "
                    "removed and stripping best/dual-audio status"
                )
            known_torrent.removed_from_seadex = True
            known_torrent.is_best = False
            known_torrent.dual_audio = False
            merged_torrents.append(known_torrent)
        else:
            log(f"Removing torrent {torrent_id} - no longer found and not chosen/preferred")

    # 2. Add new torrents that are in found_torrents but not in known_torrents
    for torrent_id, found_torrent in found_torrents_dict.items():
        if torrent_id not in known_torrents_dict:
            merged_torrents.append(found_torrent)
            if found_torrent.private:
                log(f"Skipping torrent {torrent_id} - private tracker")
            else:
                log(f"Added new torrent: {torrent_id}")

    # 3. A pending manual preference (picked via the WebUI's "Prefer" action
    # but not yet downloaded) pauses automatic selection entirely for this
    # entry - the human already made a call, don't second-guess it with an
    # auto-picked download until they explicitly hit "Download" themselves.
    # A removed-from-Seadex torrent doesn't count, even if still marked
    # preferred - it shouldn't get to freeze automatic selection forever.
    preferred_pending = next(
        (t for t in merged_torrents if t.preferred and not t.chosen and not t.removed_from_seadex),
        None,
    )
    if preferred_pending is not None:
        log(
            f"Torrent {preferred_pending.id} is marked preferred and not yet "
            "downloaded - skipping automatic selection"
        )
        return [], merged_torrents

    # 4. Candidates are every currently-found, non-private torrent - not just
    # newly-discovered ones, so a previously-seen-but-never-chosen torrent
    # keeps competing on every run instead of being permanently invisible
    # after its first appearance. Torrents no longer found on Seadex (removed,
    # including a since-removed chosen torrent) are never candidates - once
    # removed, only a manual Download can act on a torrent again.
    candidates_for_best = [
        t for t in merged_torrents if t.id in found_torrents_dict and not t.private
    ]

    if not candidates_for_best:
        log("No candidate torrents available for best selection")
        return [], merged_torrents

    # Score candidate torrents
    scored_candidates = [
        (torrent, score_torrent(torrent)) for torrent in candidates_for_best
    ]

    # Find the best torrent from candidates (highest score)
    best_torrent, best_score = max(scored_candidates, key=lambda x: x[1])

    # A multi-part release (Trs.grouped_url) is downloaded/tracked as one
    # unit - expand to every part and only send the ones not already chosen,
    # so a new part appearing later doesn't re-submit ones we already have.
    siblings = _siblings_of(merged_torrents, best_torrent)
    pending = [t for t in siblings if not t.chosen]

    if not pending:
        log(
            f"Best torrent {best_torrent.id} (and its release group, if any) is "
            f"already fully chosen - no redownload needed "
            f"(score: {best_score} [{get_scoring_breakdown(best_torrent)}])"
        )
        return [], merged_torrents

    group_note = f" - {len(pending)}/{len(siblings)} part(s) pending" if len(siblings) > 1 else ""
    log(
        f"Best torrent (from {len(candidates_for_best)} candidates): {best_torrent.id} "
        f"(score: {best_score} [{get_scoring_breakdown(best_torrent)}]){group_note}"
    )
    return pending, merged_torrents


def apply_chosen_torrents(anilist_entry: AniListSeries, torrents: list[Trs]) -> bool:
    """Submit every torrent in `torrents` to qBittorrent and, per-torrent,
    only on confirmed success, mark it chosen (clearing `chosen` on every
    other torrent in the entry not in this set).

    `torrents` should be the *complete current* set for the release being
    chosen (see group_siblings) - for a standalone torrent that's just
    itself; for a multi-part release it's every part, so this correctly
    supersedes/clears any other previously-chosen release in the entry.
    Torrents already `chosen` are skipped (not re-submitted), so this is
    safe to call with a mix of already-downloaded and still-pending parts.

    Shared by the automatic best-selection path (sync_series_item) and the
    WebUI's manual torrent-override route, so both follow the same
    "chosen means actually sent" rule instead of duplicating the logic.

    Returns True only if every torrent in `torrents` ends up chosen.
    """
    target_ids = {t.id for t in torrents}

    for torrent in torrents:
        if torrent.chosen:
            continue
        if send_to_qbittorrent(torrent.info_hash, torrent.private, torrent.url):
            torrent.chosen = True
            log(
                f"Marked torrent {torrent.id} as chosen for AniList ID {anilist_entry.anilist_id}"
            )
        else:
            log(f"Send failed for {torrent.id} - leaving unchosen, will retry next run")

    for t in anilist_entry.torrents:
        if t.id not in target_ids:
            t.chosen = False

    return all(t.chosen for t in torrents)


def mark_torrents_downloaded(anilist_entry: AniListSeries, torrents: list[Trs]) -> None:
    """Mark every torrent in `torrents` as chosen with NO qBittorrent call at
    all - for a release the user already has (grabbed before the app existed,
    or outside it) and just wants recorded, not re-downloaded. Clears
    `chosen` on every other torrent in the entry not in this set, same
    invariant as apply_chosen_torrents.

    Unlike set_preferred_torrents, this does NOT refuse on a
    removed_from_seadex torrent - confirming you already have something is a
    legitimate historical record even if SeaDex has since delisted it; it
    doesn't re-enable any automation, it just stops the auto-scorer from
    trying to replace it.
    """
    target_ids = {t.id for t in torrents}
    for t in anilist_entry.torrents:
        t.chosen = t.id in target_ids
    log(
        f"Marked {[t.id for t in torrents]} as downloaded (no send) for "
        f"AniList ID {anilist_entry.anilist_id}"
    )


def set_preferred_torrents(anilist_entry: AniListSeries, torrents: list[Trs]) -> bool:
    """Mark every torrent in `torrents` as the user's manual pick for this
    entry, with no network call. Clears `preferred` on every other torrent
    in the entry not in this set.

    `torrents` should be the complete current set for a release (see
    group_siblings) - preferring one part of a multi-part release prefers
    the whole thing. This is purely a bookkeeping action - it doesn't submit
    anything to qBittorrent (use apply_chosen_torrents for that) and it
    pauses automatic best-selection for this entry until the user explicitly
    downloads something (see the preferred-pending check in
    choose_best_and_merge_torrents).

    Refuses (returns False, no changes made) if any torrent in `torrents`
    has been removed from Seadex - only a manual Download is allowed then.
    """
    if any(t.removed_from_seadex for t in torrents):
        log(
            f"Refusing to prefer {[t.id for t in torrents]} - at least one has "
            "been removed from Seadex, only a manual download is allowed"
        )
        return False

    target_ids = {t.id for t in torrents}
    for t in anilist_entry.torrents:
        t.preferred = t.id in target_ids
    log(
        f"Marked {[t.id for t in torrents]} as preferred for AniList ID {anilist_entry.anilist_id}"
    )
    return True


def pause_series(series_item: Series) -> None:
    """Ignore every currently-known AniList entry for series_item - stops
    auto-downloading new/alternate releases for all of them, without
    touching Sonarr's monitoring or removing anything from the library.

    A future season discovered later via refresh_anilist_mapping still
    defaults to ignore=False (see AniListSeries.ignore), so it's unaffected
    by a prior pause and gets auto-synced/downloaded normally - that's what
    makes "pause this show but still grab future seasons" work with no
    separate series-level flag needed.
    """
    for entry in series_item.anilist_entries:
        entry.ignore = True
    log(f"Paused {len(series_item.anilist_entries)} AniList entr(y/ies) for '{series_item.title}'")


def resume_series(series_item: Series) -> None:
    """Un-ignore every currently-known AniList entry for series_item."""
    for entry in series_item.anilist_entries:
        entry.ignore = False
    log(f"Resumed {len(series_item.anilist_entries)} AniList entr(y/ies) for '{series_item.title}'")


def refresh_anilist_mapping(series_item: Series, anilist: AniListClient) -> None:
    """Refresh series_item's AniList entries via TVDB mapping or title search, in place."""
    found_anilist_entries: list[AniListSeries] = []

    # Try to use TVDB ID mapping first (more reliable)
    if series_item.tvdb_id:
        found_anilist_entries = anilist.get_series_by_tvdb_id(series_item.tvdb_id)

    # Fallback to title search if ID mapping didn't work
    if not found_anilist_entries:
        log(
            f"No ID mapping found for '{series_item.title}' (TVDB: {series_item.tvdb_id}), falling back to title search"
        )
        found_anilist_entries = anilist.search_anilist(series_item.title)

    # Never let a manually-removed mapping come back via title/TVDB search.
    if series_item.blacklisted_anilist_ids:
        before = len(found_anilist_entries)
        found_anilist_entries = [
            e for e in found_anilist_entries
            if e.anilist_id not in series_item.blacklisted_anilist_ids
        ]
        if len(found_anilist_entries) < before:
            log(
                f"Filtered out {before - len(found_anilist_entries)} blacklisted "
                f"AniList match(es) for '{series_item.title}'"
            )

    if found_anilist_entries:
        series_item.anilist_entries = merge_anilist_ids(
            series_item.anilist_entries, found_anilist_entries
        )
    else:
        log(f"No AniList results found for '{series_item.title}'")


def resync_seadex_torrents(
    series_item: Series, seadex: SeadexClient, skip_qbittorrent: bool = False
) -> None:
    """Re-search Seadex and choose/send the best torrent for every non-ignored AniList entry."""
    for anilist_entry in series_item.anilist_entries:
        if anilist_entry.ignore:
            continue
        log(f"Searching Seadex for AniList ID {anilist_entry.anilist_id}...")
        torrents, notes, seadex_updated_at = seadex.get_seadex_releases(anilist_entry.anilist_id)
        anilist_entry.notes = notes
        anilist_entry.seadex_updated_at = seadex_updated_at
        pending, anilist_entry.torrents = choose_best_and_merge_torrents(
            anilist_entry.torrents, torrents
        )
        if pending:
            log(
                f"Best release for AniList ID {anilist_entry.anilist_id}: "
                f"{[t.id for t in pending]}"
            )
            if skip_qbittorrent:
                log(
                    "Population pass: found candidate(s) "
                    f"{[t.id for t in pending]} for {anilist_entry.anilist_id}, "
                    "not marking chosen (no send attempted)"
                )
            else:
                # Expand to the release's full current set (not just the
                # pending parts) so apply_chosen_torrents can correctly clear
                # `chosen` on any other release in the entry.
                full_group = group_siblings(anilist_entry, pending[0])
                apply_chosen_torrents(anilist_entry, full_group)


def sync_series_item(
    series_item: Series,
    anilist: AniListClient,
    seadex: SeadexClient,
    skip_qbittorrent: bool = False,
) -> None:
    """Update AniList mappings and Seadex torrents for a single series in place."""
    refresh_anilist_mapping(series_item, anilist)
    resync_seadex_torrents(series_item, seadex, skip_qbittorrent)


def refresh_series_from_sonarr(series_item: Series) -> None:
    """Refresh series_item's Sonarr-sourced fields (tvdb_id, title, num_seasons,
    title_slug) from Sonarr, in place. No-op if Sonarr can't be reached.

    This is what actually fixes stale tvdb_id/title_slug: a per-series resync
    otherwise never talks to Sonarr at all, so a series added before these
    fields existed (or before it had a TVDB match) would never pick them up.
    """
    fresh = SonarrClient().get_series_by_id(series_item.sonarr_id)
    if fresh is None:
        log(f"Could not refresh '{series_item.title}' from Sonarr - keeping cached data")
        return

    series_item.title = fresh.title
    series_item.num_seasons = fresh.num_seasons
    if fresh.tvdb_id is not None:
        series_item.tvdb_id = fresh.tvdb_id
    if fresh.title_slug is not None:
        series_item.title_slug = fresh.title_slug


def update_all_series(skip_qbittorrent=False):
    """Main Running Loop for the script."""
    sonarr = SonarrClient()
    anilist = AniListClient()
    seadex = SeadexClient()

    # 1. Update Sonarr monitered series list.
    sonarr_series: list[Series] | None = sonarr.get_monitored_series()
    known_series: list[Series] = load_json(KNOWN_SERIES_FILE, default=[])

    # Migrate series data for backward compatibility
    known_series = migrate_series_data(known_series)

    # If we couldn't fetch series from Sonarr, don't modify the known series
    if sonarr_series is None:
        log(
            "Skipping series sync due to Sonarr connection error - keeping existing series"
        )
        series = known_series
    else:
        series: list[Series] = sync_sonarr_series(known_series, sonarr_series)

    # 2. Update AniList IDs and Seadex torrents for every series.
    for series_item in series:
        sync_series_item(series_item, anilist, seadex, skip_qbittorrent)

    with sync_manager.DATA_LOCK:
        save_json(KNOWN_SERIES_FILE, series)


def update_single_series(sonarr_id: int, skip_qbittorrent: bool = False) -> bool:
    """Fully resync a single already-known series by its Sonarr ID: refreshes
    Sonarr-sourced fields, then AniList mapping, then Seadex torrents.
    Returns False if no known series matches sonarr_id.
    """
    anilist = AniListClient()
    seadex = SeadexClient()

    known_series: list[Series] = load_json(KNOWN_SERIES_FILE, default=[])
    target = next((s for s in known_series if s.sonarr_id == sonarr_id), None)
    if target is None:
        log(f"update_single_series: no known series with sonarr_id={sonarr_id}")
        return False

    refresh_series_from_sonarr(target)
    sync_series_item(target, anilist, seadex, skip_qbittorrent)

    with sync_manager.DATA_LOCK:
        save_json(KNOWN_SERIES_FILE, known_series)
    return True


def research_series_torrents(sonarr_id: int) -> bool:
    """Re-search Seadex for a single already-known series' existing AniList
    entries only - no Sonarr or AniList API calls, so it can't reintroduce a
    bad title-search match. Returns False if no known series matches sonarr_id.
    """
    seadex = SeadexClient()

    known_series: list[Series] = load_json(KNOWN_SERIES_FILE, default=[])
    target = next((s for s in known_series if s.sonarr_id == sonarr_id), None)
    if target is None:
        log(f"research_series_torrents: no known series with sonarr_id={sonarr_id}")
        return False

    resync_seadex_torrents(target, seadex)

    with sync_manager.DATA_LOCK:
        save_json(KNOWN_SERIES_FILE, known_series)
    return True


def webhook_event_handler(event_type: str, webhook_data: dict):
    """Handle webhook events from Sonarr."""
    log(f"Processing webhook event: {event_type}")

    try:
        # Run immediate update for relevant events
        if event_type in ["SeriesAdd", "SeriesDelete", "SeriesEdit"]:
            log(f"Webhook event '{event_type}' triggered immediate series update")
            sync_manager.run_full_sync(trigger_source="webhook")
        elif event_type == "Test":
            log("Webhook test successful - no action needed")
        else:
            log(f"Webhook event '{event_type}' - no specific action defined")

    except Exception as e:
        log(f"Error handling webhook event '{event_type}': {e}")


_DISABLED_POLL_SECONDS = 60  # how often to re-check whether auto-sync has been re-enabled


def scheduled_update():
    """Continuously run update_all_series on schedule, unless disabled
    (sync interval <= 0 - manual sync only).

    A disabled interval suppresses the one-time STARTUP_SCAN population pass
    too, not just the recurring loop - that pass otherwise re-runs on every
    container restart/update regardless of the user's "manual only" intent,
    which would defeat the point. `first_scan` stays pending across disabled
    poll cycles, so if the user later raises the interval above 0 from
    Settings, the deferred population pass runs then, on the first cycle
    sync is actually allowed, instead of being skipped forever.
    """

    first_scan = STARTUP_SCAN
    warned_disabled = False

    while True:
        interval = sync_manager.get_sync_interval()

        if interval <= 0:
            if not warned_disabled:
                log(
                    "Automatic sync (including the startup population scan, if any) is "
                    "disabled - sync interval is 0. Manual sync only until re-enabled from Settings."
                )
                warned_disabled = True
            sync_manager.set_next_scheduled_at(None)
            time.sleep(_DISABLED_POLL_SECONDS)
            continue

        warned_disabled = False

        try:
            if first_scan:
                log("Performing initial data population (fetching series and torrent info)...")
                log("This will populate the cache but not send any torrents to qBittorrent")

            log("Starting scheduled update...")
            sync_manager.run_full_sync(
                trigger_source="scheduled", skip_qbittorrent=first_scan
            )

            if first_scan:
                log("Initial scan completed, will now run scheduled updates")
                first_scan = False

            interval = sync_manager.get_sync_interval()
            if interval <= 0:
                continue  # just became disabled - loop back to the pause branch above

            sync_manager.set_next_scheduled_at(time.time() + interval)
            log(f"Scheduled update completed. Next update in {interval} seconds...")
            time.sleep(interval)

        except KeyboardInterrupt:
            log("Scheduled update received interrupt signal, shutting down...")
            break
        except Exception as e:
            interval = sync_manager.get_sync_interval()
            log(f"Error in scheduled update: {e}")
            if interval <= 0:
                continue  # disabled mid-retry - loop back to the pause branch above
            log(f"Retrying in {interval} seconds...")
            time.sleep(interval)


def main():
    """Main entry point for the script."""
    log("Starting Seadex Sonarr Monitor...")
    _interval = sync_manager.get_sync_interval()
    if _interval <= 0:
        log("Automatic sync: disabled (manual sync only)")
    else:
        log(f"Sync interval: {_interval} seconds ({_interval // 3600} hours)")
    log(f"Webhook processing: {'Enabled' if USE_WEBHOOK else 'Disabled'}")

    # Start scheduled updates in a background thread.
    log("Starting scheduled updates thread...")
    scheduled_thread = threading.Thread(target=scheduled_update, daemon=True)
    scheduled_thread.start()

    # The web server hosts both the dashboard/WebUI and the /webhook route on
    # a single port - it always runs so the UI is reachable even when
    # USE_WEBHOOK is false (that flag only gates whether /webhook acts on
    # incoming Sonarr events).
    import uvicorn

    from webapp.app import app

    log(f"Starting web server on http://{WEBHOOK_HOST}:{WEBHOOK_PORT}")
    log(f"  Dashboard: http://{WEBHOOK_HOST}:{WEBHOOK_PORT}/")
    log(f"  Sonarr webhook URL: http://{WEBHOOK_HOST}:{WEBHOOK_PORT}/webhook")
    if not USE_WEBHOOK:
        log("  (webhook events will be logged but ignored - enable USE_WEBHOOK to act on them)")

    try:
        uvicorn.run(app, host=WEBHOOK_HOST, port=WEBHOOK_PORT, log_level="warning")
    except KeyboardInterrupt:
        log("Shutting down gracefully...")


if __name__ == "__main__":
    main()
