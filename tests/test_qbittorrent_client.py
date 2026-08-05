"""Tests for clients.qbittorrent_client.send_to_qbittorrent - no real network
call, no real qBittorrent instance touched. qb_client._get_client() is
monkeypatched to return a fake qbittorrentapi.Client with controllable
auth_log_in()/torrents_add() behavior.
"""
import qbittorrentapi

import clients.qbittorrent_client as qb_client


class _FakeClient:
    def __init__(self, login_exc=None, add_result="Ok.", add_exc=None):
        self.login_exc = login_exc
        self.add_result = add_result
        self.add_exc = add_exc
        self.login_called = False
        self.add_kwargs = None

    def auth_log_in(self):
        self.login_called = True
        if self.login_exc:
            raise self.login_exc

    def torrents_add(self, **kwargs):
        self.add_kwargs = kwargs
        if self.add_exc:
            raise self.add_exc
        return self.add_result


def _patch_client(monkeypatch, fake_client):
    monkeypatch.setattr(qb_client, "_get_client", lambda: fake_client)


def test_successful_submission_with_category(monkeypatch):
    fake = _FakeClient(add_result="Ok.")
    _patch_client(monkeypatch, fake)
    monkeypatch.setattr(qb_client.sync_manager, "get_qb_category", lambda: "anime-sonarr")

    result = qb_client.send_to_qbittorrent("abc123")

    assert result is True
    assert fake.login_called is True
    assert fake.add_kwargs["urls"] == "magnet:?xt=urn:btih:abc123"
    assert fake.add_kwargs["category"] == "anime-sonarr"


def test_submission_without_category(monkeypatch):
    fake = _FakeClient(add_result="Ok.")
    _patch_client(monkeypatch, fake)
    monkeypatch.setattr(qb_client.sync_manager, "get_qb_category", lambda: "")

    assert qb_client.send_to_qbittorrent("abc123") is True
    assert fake.add_kwargs["category"] is None


def test_legacy_fails_response_is_a_failure(monkeypatch):
    fake = _FakeClient(add_result="Fails.")
    _patch_client(monkeypatch, fake)

    assert qb_client.send_to_qbittorrent("abc123") is False


def test_newer_api_dict_response_is_a_success(monkeypatch):
    # Newer qBittorrent/API versions return structured metadata (not the
    # string "Ok.") on success - genuine failures raise an exception
    # instead, so any non-string return here already means success.
    fake = _FakeClient(add_result={"hash": "abc123"})
    _patch_client(monkeypatch, fake)

    assert qb_client.send_to_qbittorrent("abc123") is True


def test_login_failed_returns_false_without_submitting(monkeypatch):
    fake = _FakeClient(login_exc=qbittorrentapi.LoginFailed())
    _patch_client(monkeypatch, fake)

    assert qb_client.send_to_qbittorrent("abc123") is False
    assert fake.add_kwargs is None


def test_forbidden_ban_returns_false_without_submitting(monkeypatch):
    fake = _FakeClient(login_exc=qbittorrentapi.Forbidden403Error())
    _patch_client(monkeypatch, fake)

    assert qb_client.send_to_qbittorrent("abc123") is False
    assert fake.add_kwargs is None


def test_connection_error_returns_false(monkeypatch):
    fake = _FakeClient(login_exc=qbittorrentapi.APIConnectionError("connection refused"))
    _patch_client(monkeypatch, fake)

    assert qb_client.send_to_qbittorrent("abc123") is False


def test_torrents_add_exception_returns_false(monkeypatch):
    fake = _FakeClient(add_exc=qbittorrentapi.Conflict409Error("already added"))
    _patch_client(monkeypatch, fake)

    assert qb_client.send_to_qbittorrent("abc123") is False


def test_private_torrent_skipped_before_any_connection_attempt(monkeypatch):
    fake = _FakeClient()
    _patch_client(monkeypatch, fake)

    result = qb_client.send_to_qbittorrent("abc123", is_private=True, torrent_url="http://example/t")

    assert result is False
    assert fake.login_called is False  # never even tried to connect


def test_redacted_hash_with_no_url_skipped(monkeypatch):
    fake = _FakeClient()
    _patch_client(monkeypatch, fake)

    result = qb_client.send_to_qbittorrent("<redacted>")

    assert result is False
    assert fake.login_called is False
