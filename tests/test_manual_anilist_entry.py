"""Tests for main.py's add_manual_anilist_entry - the fix for "adding an
AniList entry manually wipes out the auto-matched entries." That bug came
from the route calling merge_anilist_ids with a found_entries list
containing only the one entry being added, which merge_anilist_ids (built
for reconciling against a *complete* fresh search) interpreted as "every
other known entry has disappeared." add_manual_anilist_entry never touches
any entry but the one being added.
"""
import main


def _entry(anilist_id, season_year=2024, manually_added=False):
    return main.AniListSeries(
        anilist_id=anilist_id, title=f"T{anilist_id}", season_year=season_year,
        manually_added=manually_added,
    )


def _series(entries):
    return main.Series(sonarr_id=1, title="Test Show", num_seasons=len(entries), anilist_entries=entries)


def test_adding_new_entry_leaves_existing_auto_matched_entries_untouched():
    auto1, auto2 = _entry(1), _entry(2)
    series = _series([auto1, auto2])
    new_entry = _entry(3, season_year=2025)

    main.add_manual_anilist_entry(series, new_entry)

    ids = {e.anilist_id for e in series.anilist_entries}
    assert ids == {1, 2, 3}
    assert auto1 in series.anilist_entries
    assert auto2 in series.anilist_entries
    assert auto1.manually_added is False
    assert auto2.manually_added is False


def test_new_entry_is_marked_manually_added():
    series = _series([])
    new_entry = _entry(5)

    main.add_manual_anilist_entry(series, new_entry)

    assert series.anilist_entries[0].manually_added is True


def test_adding_already_known_entry_marks_it_manual_without_duplicating():
    existing = _entry(7, manually_added=False)
    series = _series([existing])
    duplicate = _entry(7)

    main.add_manual_anilist_entry(series, duplicate)

    assert len(series.anilist_entries) == 1
    assert series.anilist_entries[0] is existing
    assert existing.manually_added is True


def test_result_stays_sorted_with_none_year_last():
    series = _series([_entry(1, season_year=2022)])
    main.add_manual_anilist_entry(series, _entry(2, season_year=None))
    main.add_manual_anilist_entry(series, _entry(3, season_year=2020))

    assert [e.anilist_id for e in series.anilist_entries] == [3, 1, 2]
