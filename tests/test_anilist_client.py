"""Tests for clients.anilist_client.AniListClient - specifically that a
result with a null seasonYear (AniList's schema allows this; donghua/CN
content in particular is often not tagged with one) isn't silently dropped.
No real network call - _make_request_with_retry is monkeypatched to return
a canned response mirroring the real AniList "Soulmate Adventure" payload
(AniList ID 101843) that originally exposed this bug.
"""
from clients.anilist_client import AniListClient

_SOULMATE_ADVENTURE_MEDIA = {
    "id": 101843,
    "title": {"romaji": "Feng Ling Yu Xiu", "english": "Soulmate Adventure", "native": "风灵玉秀"},
    "format": "ONA",
    "episodes": 12,
    "seasonYear": None,
    "status": "FINISHED",
}


def _canned_response(media_list):
    return {"data": {"Page": {"media": media_list}}}


def test_search_anilist_does_not_drop_null_season_year(monkeypatch):
    client = AniListClient()
    monkeypatch.setattr(
        client, "_make_request_with_retry",
        lambda query, variables, max_retries=3: _canned_response([_SOULMATE_ADVENTURE_MEDIA]),
    )

    results = client.search_anilist("Soulmate Adventure")

    assert len(results) == 1
    assert results[0].anilist_id == 101843
    assert results[0].title == "Soulmate Adventure"
    assert results[0].season_year is None


def test_get_series_by_anilist_ids_does_not_drop_null_season_year(monkeypatch):
    client = AniListClient()
    media = dict(_SOULMATE_ADVENTURE_MEDIA)
    monkeypatch.setattr(
        client, "_make_request_with_retry",
        lambda query, variables, max_retries=3: _canned_response([media]),
    )

    results = client.get_series_by_anilist_ids([101843])

    assert len(results) == 1
    assert results[0].anilist_id == 101843
    assert results[0].season_year is None


def test_search_anilist_sorts_null_year_after_known_years(monkeypatch):
    known_year = dict(_SOULMATE_ADVENTURE_MEDIA, id=1, seasonYear=2020)
    null_year = dict(_SOULMATE_ADVENTURE_MEDIA, id=2, seasonYear=None)

    client = AniListClient()
    monkeypatch.setattr(
        client, "_make_request_with_retry",
        lambda query, variables, max_retries=3: _canned_response([null_year, known_year]),
    )

    results = client.search_anilist("whatever")

    assert [r.anilist_id for r in results] == [1, 2]


def test_search_anilist_still_requires_anilist_id(monkeypatch):
    missing_id = dict(_SOULMATE_ADVENTURE_MEDIA)
    missing_id["id"] = None

    client = AniListClient()
    monkeypatch.setattr(
        client, "_make_request_with_retry",
        lambda query, variables, max_retries=3: _canned_response([missing_id]),
    )

    assert client.search_anilist("whatever") == []
