"""Main script for Seaex Sonarr Monitor."""

import time
import threading
from data_class import Series, AniListSeries, Trs

from cache import load_json, save_json
from utils import log
from config import (
    KNOWN_SERIES_FILE,
    SYNC_INTERVAL,
    WEBHOOK_HOST,
    WEBHOOK_PORT,
    USE_WEBHOOK,
    SCORING_IS_BEST_WEIGHT,
    SCORING_DUAL_AUDIO_WEIGHT,
    SCORING_TRACKER_WEIGHTS,
    STARTUP_SCAN,
)
from webhook_server import WebhookServer

from qbittorrent_client import send_to_qbittorrent
from sonarr_client import SonarrClient
from anilist_client import AniListClient
from seadex_client import SeadexClient


def sync_sonarr_series(
    known_series: list[Series], sonarr_series: list[Series]
) -> list[Series]:
    """Sync Known series with Sonarr series, adding or removing as necessary."""
    # Create dictionaries for easier lookup by sonarr_id
    known_series_dict = {series.sonarr_id: series for series in known_series}
    sonarr_series_dict = {series.sonarr_id: series for series in sonarr_series}

    # Start with existing known series that are still in Sonarr
    synced_series = []

    # 1. Keep existing series that are still monitored in Sonarr (don't modify them)
    for sonarr_id, known_series_item in known_series_dict.items():
        if sonarr_id in sonarr_series_dict:
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


def choose_best_and_merge_torrents(
    known_torrents: list[Trs], found_torrents: list[Trs]
) -> tuple[Trs | None, list[Trs]]:
    """Choose the best torrent from found_torrents and merge with known_torrents."""
    # Create dictionaries for easier lookup by torrent id
    known_torrents_dict = {torrent.id: torrent for torrent in known_torrents}
    found_torrents_dict = {torrent.id: torrent for torrent in found_torrents}

    merged_torrents = []
    candidates_for_best = []
    original_chosen_status: set[str] = set()

    # 1. Keep existing torrents that are still found or are marked as chosen
    # Store original chosen status before modifying
    for torrent_id, known_torrent in known_torrents_dict.items():
        # Store original chosen status
        if known_torrent.chosen:
            original_chosen_status.add(torrent_id)
            candidates_for_best.append(known_torrent)

        # Keep torrents that are still found or were originally chosen
        if torrent_id in found_torrents_dict or known_torrent.chosen:
            known_torrent.chosen = False  # Reset chosen status
            merged_torrents.append(known_torrent)
        else:
            log(f"Removing torrent {torrent_id} - no longer found and not chosen")

    # 2. Add new torrents that are in found_torrents but not in known_torrents
    for torrent_id, found_torrent in found_torrents_dict.items():
        if torrent_id not in known_torrents_dict:
            merged_torrents.append(found_torrent)
            if found_torrent.private:
                log(f"Skipping torrent {torrent_id} - private tracker")
                continue
            candidates_for_best.append(found_torrent)
            log(f"Added new torrent: {torrent_id}")

    # 4. Find the best torrent from candidates only
    if not candidates_for_best:
        log("No candidate torrents available for best selection")
        # If no candidates, just return merged list with no torrent chosen
        return None, merged_torrents

    # Score candidate torrents
    scored_candidates = [
        (torrent, score_torrent(torrent)) for torrent in candidates_for_best
    ]

    # Find the best torrent from candidates (highest score)
    best_torrent, best_score = max(scored_candidates, key=lambda x: x[1])

    if best_torrent.id in original_chosen_status:
        log(
            f"Best torrent {best_torrent.id} was already chosen - no redownload needed "
            f"(score: {best_score} [{get_scoring_breakdown(best_torrent)}])"
        )
        return None, merged_torrents

    # 5. Set the best torrent as chosen, all others as not chosen
    best_torrent.chosen = True

    log(
        f"Best torrent (from {len(candidates_for_best)} candidates): {best_torrent.id} "
        f"(score: {best_score} [{get_scoring_breakdown(best_torrent)}])"
    )
    return best_torrent, merged_torrents


def update_all_series():
    """Main Running Loop for the script."""
    sonarr = SonarrClient()
    anilist = AniListClient()
    seadex = SeadexClient()

    # 1. Update Sonarr monitered series list.
    sonarr_series: list[Series] = sonarr.get_monitored_series()
    known_series: list[Series] = load_json(KNOWN_SERIES_FILE, default=[])
    series: list[Series] = sync_sonarr_series(known_series, sonarr_series)

    # 2. Update AniList IDs for all series.
    for series_item in series:
        found_anilist_entries: list[AniListSeries] = anilist.search_anilist(
            series_item.title
        )
        if found_anilist_entries:
            series_item.anilist_entries = merge_anilist_ids(
                series_item.anilist_entries, found_anilist_entries
            )
        else:
            log(f"No AniList results found for '{series_item.title}'")

        # 3. Search seadex for all AniList IDs.
        for anilist_entry in series_item.anilist_entries:
            if anilist_entry.ignore:
                continue
            log(f"Searching Seadex for AniList ID {anilist_entry.anilist_id}...")
            torrents: list[Trs] = seadex.get_seadex_releases(anilist_entry.anilist_id)
            best, anilist_entry.torrents = choose_best_and_merge_torrents(
                anilist_entry.torrents, torrents
            )
            if best:
                log(
                    f"Best release for AniList ID {anilist_entry.anilist_id}: {best.id}"
                )
                send_to_qbittorrent(best.info_hash, best.private, best.url)

    save_json(KNOWN_SERIES_FILE, series)


def webhook_event_handler(event_type: str, webhook_data: dict):
    """Handle webhook events from Sonarr."""
    log(f"Processing webhook event: {event_type}")

    try:
        # Run immediate update for relevant events
        if event_type in ["SeriesAdd", "SeriesDelete", "SeriesEdit"]:
            log(f"Webhook event '{event_type}' triggered immediate series update")
            update_all_series()
        elif event_type == "Test":
            log("Webhook test successful - no action needed")
        else:
            log(f"Webhook event '{event_type}' - no specific action defined")

    except Exception as e:
        log(f"Error handling webhook event '{event_type}': {e}")


def scheduled_update():
    """Continuously run update_all_series on schedule."""

    while True:
        try:
            log("Starting scheduled update...")
            update_all_series()

            log(
                f"Scheduled update completed. Next update in {SYNC_INTERVAL} seconds..."
            )
            time.sleep(SYNC_INTERVAL)

        except KeyboardInterrupt:
            log("Scheduled update received interrupt signal, shutting down...")
            break
        except Exception as e:
            log(f"Error in scheduled update: {e}")
            log(f"Retrying in {SYNC_INTERVAL} seconds...")
            time.sleep(SYNC_INTERVAL)


def main():
    """Main entry point for the script."""
    log("Starting Seadex Sonarr Monitor...")
    log(f"Sync interval: {SYNC_INTERVAL} seconds ({SYNC_INTERVAL // 3600} hours)")
    log(f"Webhook mode: {'Enabled' if USE_WEBHOOK else 'Disabled'}")

    webhook_server = None

    try:
        # Start webhook server if enabled
        if USE_WEBHOOK:
            log("Webhook mode enabled - starting webhook server...")
            webhook_server = WebhookServer(host=WEBHOOK_HOST, port=WEBHOOK_PORT)
            webhook_server.set_event_callback(webhook_event_handler)
            webhook_server.start()

            log("Configure Sonarr Connection/Webhook:")
            log(f"  URL: http://{WEBHOOK_HOST}:{WEBHOOK_PORT}/webhook")
            log("  Method: POST")
            log("  Triggers: On Series Add, On Series Delete, On Series Update")
        else:
            log("Webhook mode disabled - using scheduled updates only")

        # Run initial update
        log("Running initial update...")

        if STARTUP_SCAN:
            update_all_series()

        # Start scheduled updates in a separate thread
        log("Starting scheduled updates thread...")
        scheduled_thread = threading.Thread(target=scheduled_update, daemon=True)
        scheduled_thread.start()

        # Main thread keeps the program alive and handles shutdown
        log("Monitor started successfully!")
        if not USE_WEBHOOK:
            log(f"Will check for updates every {SYNC_INTERVAL // 3600} hours")
        log("Press Ctrl+C to stop...")

        # Keep main thread alive
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        log("Shutting down gracefully...")
    except Exception as e:
        log(f"Fatal error in main: {e}")
        raise
    finally:
        # Stop webhook server if it was started
        if webhook_server and webhook_server.is_running():
            webhook_server.stop()


if __name__ == "__main__":
    main()
