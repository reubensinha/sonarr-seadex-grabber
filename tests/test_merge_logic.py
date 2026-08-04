"""Tests for main.py's choose_best_and_merge_torrents and the chosen/preferred
action helpers. All network calls (send_to_qbittorrent) are monkeypatched -
these tests never touch a real qBittorrent instance or the filesystem.
"""
import main


def _set_weights(monkeypatch, is_best=5, dual_audio=1, tracker_weights=None):
    monkeypatch.setattr(main, "SCORING_IS_BEST_WEIGHT", is_best)
    monkeypatch.setattr(main, "SCORING_DUAL_AUDIO_WEIGHT", dual_audio)
    monkeypatch.setattr(
        main, "SCORING_TRACKER_WEIGHTS", tracker_weights or {"Nyaa": 0, "default": 0}
    )


def _torrent(id_, **overrides):
    defaults = dict(
        id=id_, info_hash=f"hash-{id_}", tracker="Nyaa", url=f"http://example/{id_}",
        is_best=False, dual_audio=False,
    )
    defaults.update(overrides)
    return main.Trs(**defaults)


def _entry(torrents):
    return main.AniListSeries(anilist_id=1, title="Test", season_year=2024, torrents=torrents)


# --- choose_best_and_merge_torrents -----------------------------------------

def test_new_torrent_is_added_as_candidate():
    found = [_torrent("a", is_best=True)]
    pending, merged = main.choose_best_and_merge_torrents([], found)
    assert [t.id for t in pending] == ["a"]
    assert [t.id for t in merged] == ["a"]


def test_no_candidates_returns_empty():
    pending, merged = main.choose_best_and_merge_torrents([], [])
    assert pending == []
    assert merged == []


def test_private_torrent_is_not_a_candidate():
    found = [_torrent("a", private=True)]
    pending, merged = main.choose_best_and_merge_torrents([], found)
    assert pending == []
    assert [t.id for t in merged] == ["a"]


def test_already_chosen_best_is_not_resent():
    known = [_torrent("a", is_best=True, chosen=True)]
    found = [_torrent("a", is_best=True)]
    pending, merged = main.choose_best_and_merge_torrents(known, found)
    assert pending == []
    assert merged[0].chosen is True


def test_higher_scoring_new_torrent_still_becomes_pending(monkeypatch):
    _set_weights(monkeypatch)
    known = [_torrent("a", chosen=True)]
    found = [_torrent("a"), _torrent("b", is_best=True)]
    pending, merged = main.choose_best_and_merge_torrents(known, found)
    assert [t.id for t in pending] == ["b"]


def test_torrent_removed_from_seadex_is_marked_and_stripped():
    known = [_torrent("a", is_best=True, dual_audio=True, chosen=True)]
    pending, merged = main.choose_best_and_merge_torrents(known, [])
    assert pending == []
    assert len(merged) == 1
    t = merged[0]
    assert t.removed_from_seadex is True
    assert t.is_best is False
    assert t.dual_audio is False
    assert t.chosen is True  # historical record preserved


def test_unpreferred_unchosen_torrent_dropped_when_gone_from_seadex():
    known = [_torrent("a")]  # never chosen or preferred
    _, merged = main.choose_best_and_merge_torrents(known, [])
    assert merged == []


def test_removed_torrent_is_not_a_future_candidate():
    known = [_torrent("a", is_best=True, chosen=True)]
    _, merged = main.choose_best_and_merge_torrents(known, [])
    assert merged[0].removed_from_seadex is True
    pending, _ = main.choose_best_and_merge_torrents(merged, [])
    assert pending == []


def test_reappearing_torrent_clears_removed_flag():
    known = [_torrent("a", chosen=True, removed_from_seadex=True)]
    found = [_torrent("a", is_best=True)]
    _, merged = main.choose_best_and_merge_torrents(known, found)
    assert merged[0].removed_from_seadex is False
    assert merged[0].is_best is True


def test_pending_preferred_pick_pauses_auto_selection(monkeypatch):
    _set_weights(monkeypatch)
    known = [_torrent("a", preferred=True)]
    found = [_torrent("a"), _torrent("b", is_best=True)]
    pending, _ = main.choose_best_and_merge_torrents(known, found)
    assert pending == []


def test_removed_preferred_does_not_pause_selection(monkeypatch):
    _set_weights(monkeypatch)
    known = [_torrent("a", preferred=True, removed_from_seadex=True)]
    found = [_torrent("b", is_best=True)]
    pending, _ = main.choose_best_and_merge_torrents(known, found)
    assert [t.id for t in pending] == ["b"]


def test_grouped_release_expands_to_all_unchosen_siblings():
    found = [
        _torrent("a", is_best=True, grouped_url="g"),
        _torrent("b", is_best=True, grouped_url="g"),
    ]
    pending, _ = main.choose_best_and_merge_torrents([], found)
    assert {t.id for t in pending} == {"a", "b"}


def test_grouped_release_only_pending_for_new_parts():
    known = [_torrent("a", is_best=True, grouped_url="g", chosen=True)]
    found = [
        _torrent("a", is_best=True, grouped_url="g"),
        _torrent("b", is_best=True, grouped_url="g"),
    ]
    pending, _ = main.choose_best_and_merge_torrents(known, found)
    assert [t.id for t in pending] == ["b"]


# --- apply_chosen_torrents ---------------------------------------------------

def test_apply_chosen_torrents_marks_only_on_success(monkeypatch):
    calls = []

    def fake_send(info_hash, private, url):
        calls.append(info_hash)
        return info_hash == "hash-a"

    monkeypatch.setattr(main, "send_to_qbittorrent", fake_send)

    a, b = _torrent("a"), _torrent("b")
    entry = _entry([a, b])

    result = main.apply_chosen_torrents(entry, [a, b])

    assert calls == ["hash-a", "hash-b"]
    assert a.chosen is True
    assert b.chosen is False
    assert result is False  # not every torrent in `torrents` ended up chosen


def test_apply_chosen_torrents_skips_already_chosen(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "send_to_qbittorrent", lambda *a: calls.append(a) or True)

    a = _torrent("a", chosen=True)
    entry = _entry([a])
    main.apply_chosen_torrents(entry, [a])

    assert calls == []  # already chosen, never re-submitted


def test_apply_chosen_torrents_clears_other_chosen(monkeypatch):
    monkeypatch.setattr(main, "send_to_qbittorrent", lambda *a: True)

    old, new = _torrent("old", chosen=True), _torrent("new")
    entry = _entry([old, new])

    result = main.apply_chosen_torrents(entry, [new])

    assert result is True
    assert new.chosen is True
    assert old.chosen is False


# --- mark_torrents_downloaded / set_preferred_torrents -----------------------

def test_mark_torrents_downloaded_sends_nothing(monkeypatch):
    def fail(*_a):
        raise AssertionError("mark_torrents_downloaded must never call send_to_qbittorrent")

    monkeypatch.setattr(main, "send_to_qbittorrent", fail)

    a, b = _torrent("a"), _torrent("b", chosen=True)
    entry = _entry([a, b])
    main.mark_torrents_downloaded(entry, [a])

    assert a.chosen is True
    assert b.chosen is False  # cleared, wasn't in the target set


def test_mark_torrents_downloaded_works_on_removed_torrent():
    a = _torrent("a", removed_from_seadex=True)
    entry = _entry([a])
    main.mark_torrents_downloaded(entry, [a])
    assert a.chosen is True


def test_set_preferred_torrents_marks_pick():
    a, b = _torrent("a"), _torrent("b", preferred=True)
    entry = _entry([a, b])

    result = main.set_preferred_torrents(entry, [a])

    assert result is True
    assert a.preferred is True
    assert b.preferred is False


def test_set_preferred_torrents_refuses_if_removed_from_seadex():
    a = _torrent("a", removed_from_seadex=True)
    entry = _entry([a])

    result = main.set_preferred_torrents(entry, [a])

    assert result is False
    assert a.preferred is False
