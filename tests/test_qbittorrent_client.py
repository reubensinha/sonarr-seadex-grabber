"""Tests for clients.qbittorrent_client.qb_authenticate - no real network
call, no real qBittorrent instance touched. session.post is monkeypatched to
a fake that captures the request and returns a stub response.
"""
import clients.qbittorrent_client as qb_client


class _FakeResponse:
    def __init__(self, text):
        self.text = text


def test_login_sends_referer_and_origin_headers(monkeypatch):
    monkeypatch.setattr(qb_client, "QB_URL", "http://qbittorrent.example:8080")
    captured = {}

    def fake_post(url, data=None, headers=None):
        captured["url"] = url
        captured["data"] = data
        captured["headers"] = headers
        return _FakeResponse("Ok.")

    monkeypatch.setattr(qb_client.session, "post", fake_post)

    assert qb_client.qb_authenticate() is True
    assert captured["url"] == "http://qbittorrent.example:8080/api/v2/auth/login"
    assert captured["headers"]["Referer"] == "http://qbittorrent.example:8080"
    assert captured["headers"]["Origin"] == "http://qbittorrent.example:8080"


def test_login_failure_returns_false(monkeypatch):
    monkeypatch.setattr(
        qb_client.session, "post", lambda *a, **k: _FakeResponse("Fails.")
    )
    assert qb_client.qb_authenticate() is False


def test_login_exception_returns_false(monkeypatch):
    def raise_error(*a, **k):
        raise ConnectionError("connection refused")

    monkeypatch.setattr(qb_client.session, "post", raise_error)
    assert qb_client.qb_authenticate() is False
