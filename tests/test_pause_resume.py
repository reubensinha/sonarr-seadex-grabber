"""Tests for main.py's pause_series/resume_series - pure functions, no
network/file I/O. These bulk-toggle the existing AniListSeries.ignore flag
across a whole series' entries; no new data model field is introduced."""
import main


def _entry(anilist_id, ignore=False):
    return main.AniListSeries(anilist_id=anilist_id, title=f"T{anilist_id}", season_year=2024, ignore=ignore)


def _series(entries):
    return main.Series(sonarr_id=1, title="Test Show", num_seasons=len(entries), anilist_entries=entries)


def test_pause_series_ignores_every_entry():
    series = _series([_entry(1), _entry(2, ignore=True), _entry(3)])
    main.pause_series(series)
    assert all(e.ignore for e in series.anilist_entries)


def test_resume_series_unignores_every_entry():
    series = _series([_entry(1, ignore=True), _entry(2, ignore=True)])
    main.resume_series(series)
    assert all(not e.ignore for e in series.anilist_entries)


def test_pause_resume_no_entries_is_a_no_op():
    series = _series([])
    main.pause_series(series)  # must not raise
    main.resume_series(series)
    assert series.anilist_entries == []


def test_new_entry_defaults_unignored():
    """Documents the invariant pause/resume relies on: a future season
    discovered later is never affected by a prior pause, because a brand
    new AniListSeries always starts ignore=False."""
    fresh = main.AniListSeries(anilist_id=99, title="New Season", season_year=2025)
    assert fresh.ignore is False
