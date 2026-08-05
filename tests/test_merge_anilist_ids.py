"""Tests for main.py's merge_anilist_ids - specifically that a mix of known
and unknown (None) season_year values doesn't crash the sort and orders
sensibly. AniList's own schema allows a null seasonYear (donghua/CN-origin
anime in particular is often not tagged with one), so this must be handled,
not assumed away.
"""
import main


def _entry(anilist_id, season_year, **overrides):
    defaults = dict(anilist_id=anilist_id, title=f"T{anilist_id}", season_year=season_year)
    defaults.update(overrides)
    return main.AniListSeries(**defaults)


def test_merge_sorts_known_years_ascending():
    found = [_entry(1, 2022), _entry(2, 2020), _entry(3, 2021)]
    merged = main.merge_anilist_ids([], found)
    assert [e.anilist_id for e in merged] == [2, 3, 1]


def test_merge_does_not_crash_on_mixed_none_and_int_years():
    found = [_entry(1, 2022), _entry(2, None), _entry(3, 2020)]
    merged = main.merge_anilist_ids([], found)  # must not raise TypeError
    assert [e.anilist_id for e in merged] == [3, 1, 2]


def test_merge_all_none_years_does_not_crash():
    found = [_entry(1, None), _entry(2, None)]
    merged = main.merge_anilist_ids([], found)
    assert {e.anilist_id for e in merged} == {1, 2}


def test_merge_keeps_manually_added_entry_with_none_year():
    known = [_entry(1, None, manually_added=True)]
    merged = main.merge_anilist_ids(known, [])
    assert [e.anilist_id for e in merged] == [1]
