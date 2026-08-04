"""Data Class Representations"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict


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
    private: bool = False  # Indicates if this is a private tracker torrent
    preferred: bool = False  # Manually picked by the user, no download attempted yet
    published_at: str | None = None  # SeaDex's "created" timestamp for this release
    release_group: str | None = None  # SeaDex's "releaseGroup" for this torrent
    # True once this torrent no longer appears in SeaDex's results for its
    # AniList ID. Stripped of is_best/dual_audio and excluded from automatic
    # selection when this is set - only a manual Download still works on it.
    removed_from_seadex: bool = False
    # SeaDex's "groupedUrl" - non-None and identical across every torrent in
    # a multi-part release (e.g. per-episode releases from one group), empty
    # for standalone/batch releases. Torrents sharing this value are treated
    # as one entry - see main.py's group_siblings().
    grouped_url: str | None = None

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
    def from_dict(cls, data: Dict[str, Any]) -> "Trs":
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
    notes: str | None = None  # SeaDex's collection-entry notes, explaining release groups
    # SeaDex's collection-entry "updated" timestamp - when SeaDex staff last
    # touched this anime's release info (new torrent, edited notes, etc.),
    # not to be confused with a torrent's own publish date. Used for sorting.
    seadex_updated_at: str | None = None

    def __repr__(self):
        return (
            f"AniList_Series(id={self.anilist_id}, title='{self.title}', "
            f"season_year={self.season_year})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "anilist_id": self.anilist_id,
            "title": self.title,
            "season_year": self.season_year,
            "torrents": [torrent.to_dict() for torrent in self.torrents],
            "manually_added": self.manually_added,
            "ignore": self.ignore,
            "notes": self.notes,
            "seadex_updated_at": self.seadex_updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AniListSeries":
        """Create from dictionary for JSON deserialization."""
        torrents = [Trs.from_dict(t) for t in data.get("torrents", [])]
        return cls(
            anilist_id=data["anilist_id"],
            title=data["title"],
            season_year=data["season_year"],
            torrents=torrents,
            manually_added=data.get("manually_added", False),
            ignore=data.get("ignore", False),
            notes=data.get("notes"),
            seadex_updated_at=data.get("seadex_updated_at"),
        )


@dataclass
class Series:
    """Data class representing a series."""

    sonarr_id: int
    title: str
    num_seasons: int
    tvdb_id: int | None = None
    title_slug: str | None = None  # Sonarr's URL slug, e.g. "delicious-in-dungeon"
    anilist_entries: list[AniListSeries] = field(default_factory=list)
    # AniList IDs manually removed via the WebUI - excluded from future title/TVDB
    # search results so a removed mapping can't silently come back.
    blacklisted_anilist_ids: list[int] = field(default_factory=list)

    def __repr__(self):
        return (
            f"Series(id={self.sonarr_id}, title='{self.title}', "
            f"tvdb_id={self.tvdb_id}, anilist_ids={self.anilist_entries})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "sonarr_id": self.sonarr_id,
            "title": self.title,
            "num_seasons": self.num_seasons,
            "tvdb_id": self.tvdb_id,
            "title_slug": self.title_slug,
            "anilist_entries": [entry.to_dict() for entry in self.anilist_entries],
            "blacklisted_anilist_ids": self.blacklisted_anilist_ids,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Series":
        """Create from dictionary for JSON deserialization."""
        anilist_entries = [
            AniListSeries.from_dict(entry) for entry in data.get("anilist_entries", [])
        ]
        return cls(
            sonarr_id=data["sonarr_id"],
            title=data["title"],
            num_seasons=data["num_seasons"],
            tvdb_id=data.get("tvdb_id"),
            title_slug=data.get("title_slug"),
            anilist_entries=anilist_entries,
            blacklisted_anilist_ids=data.get("blacklisted_anilist_ids", []),
        )
