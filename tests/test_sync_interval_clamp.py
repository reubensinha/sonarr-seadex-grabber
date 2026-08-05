"""Tests for core.sync_manager.clamp_sync_interval_hours - pure function,
no network/file I/O. 0 means "disable automatic sync" and must pass through
unclamped; any positive value is floored to a 5-minute minimum."""
import core.sync_manager as sync_manager


def test_zero_stays_zero():
    assert sync_manager.clamp_sync_interval_hours(0) == 0


def test_negative_treated_as_zero():
    assert sync_manager.clamp_sync_interval_hours(-5) == 0


def test_tiny_positive_value_floored_to_minimum():
    assert sync_manager.clamp_sync_interval_hours(0.01) == sync_manager._MIN_SYNC_INTERVAL_SECONDS


def test_normal_value_converts_to_seconds():
    assert sync_manager.clamp_sync_interval_hours(2) == 7200
