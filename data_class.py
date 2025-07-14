"""Data Class Representations"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any


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

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Trs':
        """Create from dictionary for JSON deserialization."""
        return cls(**data)


@dataclass
class AniListSeries:
    """Data class representing an AniList series."""

    anilist_id: int
    title: str
    season_year: int
    torrents: list[Trs] = field(default_factory=list)
    manually_added: bool = False
    ignore: bool = False

    def __repr__(self):
        return (
            f"AniList_Series(id={self.anilist_id}, title='{self.title}', "
            f"season_year={self.season_year})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'anilist_id': self.anilist_id,
            'title': self.title,
            'season_year': self.season_year,
            'torrents': [torrent.to_dict() for torrent in self.torrents],
            'manually_added': self.manually_added,
            'ignore': self.ignore
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AniListSeries':
        """Create from dictionary for JSON deserialization."""
        torrents = [Trs.from_dict(t) for t in data.get('torrents', [])]
        return cls(
            anilist_id=data['anilist_id'],
            title=data['title'],
            season_year=data['season_year'],
            torrents=torrents,
            manually_added=data.get('manually_added', False),
            ignore=data.get('ignore', False)
        )


@dataclass
class Series:
    """Data class representing a series."""

    sonarr_id: int
    title: str
    num_seasons: int
    anilist_entries: list[AniListSeries] = field(default_factory=list)

    def __repr__(self):
        return f"Series(id={self.sonarr_id}, title='{self.title}', anilist_ids={self.anilist_entries})"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'sonarr_id': self.sonarr_id,
            'title': self.title,
            'num_seasons': self.num_seasons,
            'anilist_entries': [entry.to_dict() for entry in self.anilist_entries]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Series':
        """Create from dictionary for JSON deserialization."""
        anilist_entries = [AniListSeries.from_dict(entry) for entry in data.get('anilist_entries', [])]
        return cls(
            sonarr_id=data['sonarr_id'],
            title=data['title'],
            num_seasons=data['num_seasons'],
            anilist_entries=anilist_entries
        )
