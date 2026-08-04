"""Tests for main.py's grouped-release sibling helpers (SeaDex's grouped_url)."""
import main


def _torrent(id_, grouped_url=None):
    return main.Trs(
        id=id_, info_hash=f"hash-{id_}", tracker="Erai-raws", url=f"http://example/{id_}",
        is_best=False, dual_audio=False, grouped_url=grouped_url,
    )


def test_standalone_torrent_has_no_siblings():
    a = _torrent("a")
    b = _torrent("b")
    assert main._siblings_of([a, b], a) == [a]


def test_grouped_torrents_are_siblings():
    a = _torrent("a", grouped_url="https://nyaa/group")
    b = _torrent("b", grouped_url="https://nyaa/group")
    c = _torrent("c", grouped_url="https://nyaa/other")
    assert main._siblings_of([a, b, c], a) == [a, b]


def test_group_siblings_uses_entry_torrents():
    a = _torrent("a", grouped_url="g")
    b = _torrent("b", grouped_url="g")
    entry = main.AniListSeries(anilist_id=1, title="Test", season_year=2024, torrents=[a, b])
    assert main.group_siblings(entry, a) == [a, b]
