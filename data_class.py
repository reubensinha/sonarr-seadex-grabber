"""Data Class Representations"""

from dataclasses import dataclass


@dataclass
class Trs:
    """Data class representing a torrent release."""

    id: str
    info_hash: str
    tracker: str
    url: str
    is_best: bool
    dual_audio: bool
    chosen: bool = False

    def __repr__(self):
        return (
            f"Trs(id='{self.id}', infohase={self.info_hash}, "
            f"tracker={self.tracker}, url={self.url})"
            f" is_best={self.is_best}, dual_audio={self.dual_audio})"
        )


@dataclass
class AniListSeries:
    """Data class representing an AniList series."""

    anilist_id: int
    title: str
    season_year: int
    torrents: list[Trs] = []
    manually_added: bool = False
    ignore: bool = False

    def __post_init__(self):
        if self.torrents is None:
            self.torrents = []

    def __repr__(self):
        return (
            f"AniList_Series(id={self.anilist_id}, title='{self.title}', "
            f"season_year={self.season_year})"
        )


@dataclass
class Series:
    """Data class representing a series."""

    sonarr_id: int
    title: str
    num_seasons: int
    anilist_entries: list[AniListSeries] = []

    def __post_init__(self):
        if self.anilist_entries is None:
            self.anilist_entries = []

    def __repr__(self):
        return f"Series(id={self.sonarr_id}, title='{self.title}', anilist_ids={self.anilist_entries})"
