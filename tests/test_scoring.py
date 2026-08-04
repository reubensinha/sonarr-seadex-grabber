"""Tests for main.py's pure scoring logic - no network, no file I/O.

Scoring weights are monkeypatched to fixed values rather than relying on
whatever config.yaml/env vars happen to be present in the environment the
tests run in (a real config.yaml is gitignored and may set different
weights locally than the defaults CI sees).
"""
import main


def _set_weights(monkeypatch, is_best=2, dual_audio=1, tracker_weights=None):
    monkeypatch.setattr(main, "SCORING_IS_BEST_WEIGHT", is_best)
    monkeypatch.setattr(main, "SCORING_DUAL_AUDIO_WEIGHT", dual_audio)
    monkeypatch.setattr(
        main, "SCORING_TRACKER_WEIGHTS", tracker_weights or {"Nyaa": 0, "AB": -10, "default": 0}
    )


def _torrent(**overrides):
    defaults = dict(
        id="t1", info_hash="hash1", tracker="Nyaa", url="http://example/1",
        is_best=False, dual_audio=False,
    )
    defaults.update(overrides)
    return main.Trs(**defaults)


def test_baseline_score_is_zero(monkeypatch):
    _set_weights(monkeypatch)
    assert main.score_torrent(_torrent(tracker="Nyaa")) == 0


def test_is_best_adds_weight(monkeypatch):
    _set_weights(monkeypatch)
    assert main.score_torrent(_torrent(tracker="Nyaa", is_best=True)) == 2


def test_dual_audio_adds_weight(monkeypatch):
    _set_weights(monkeypatch)
    assert main.score_torrent(_torrent(tracker="Nyaa", dual_audio=True)) == 1


def test_tracker_penalty_applied(monkeypatch):
    _set_weights(monkeypatch)
    assert main.score_torrent(_torrent(tracker="AB")) == -10


def test_unknown_tracker_uses_default(monkeypatch):
    _set_weights(monkeypatch, tracker_weights={"Nyaa": 0, "default": -3})
    assert main.score_torrent(_torrent(tracker="SomeObscureTracker")) == -3


def test_combined_score(monkeypatch):
    _set_weights(monkeypatch)
    t = _torrent(tracker="AB", is_best=True, dual_audio=True)
    assert main.score_torrent(t) == 2 + 1 - 10


def test_breakdown_no_bonuses(monkeypatch):
    _set_weights(monkeypatch)
    assert main.get_scoring_breakdown(_torrent(tracker="Nyaa")) == "no bonuses"


def test_breakdown_lists_active_bonuses(monkeypatch):
    _set_weights(monkeypatch)
    t = _torrent(tracker="AB", is_best=True, dual_audio=True, private=True)
    breakdown = main.get_scoring_breakdown(t)
    assert "is_best: +2" in breakdown
    assert "dual_audio: +1" in breakdown
    assert "tracker(AB): -10" in breakdown
    assert "private" in breakdown
