"""Client for interacting with qBittorrent via the qbittorrent-api package -
handles CSRF headers, auth/session mechanics, and API-version differences
for us instead of us hand-rolling qBittorrent's raw Web API.
"""
import qbittorrentapi

from core import sync_manager
from core.utils import log


def _get_client() -> qbittorrentapi.Client:
    """A fresh Client per call, reading the dynamic connection-settings
    getters each time (not cached) - so a change from the Settings page
    takes effect immediately, without a restart."""
    return qbittorrentapi.Client(
        host=sync_manager.get_qb_url(),
        username=sync_manager.get_qb_user(),
        password=sync_manager.get_qb_pass(),
    )


def send_to_qbittorrent(info_hash, is_private=False, torrent_url=None) -> bool:
    """Send a torrent to qBittorrent using its info hash or URL for private torrents.

    Returns True only if the torrent was actually submitted successfully.
    """
    # Checked first, before ever attempting to connect - a private/redacted
    # torrent is skipped regardless, so there's no reason to spend a login
    # attempt on it. Fewer unnecessary attempts also matters given
    # qBittorrent auto-bans an IP after too many failed logins.
    if is_private or info_hash == "<redacted>":
        if torrent_url:
            log(
                f"Private torrent detected - would need direct download from: {torrent_url}"
            )
            log("Skipping private torrent - cannot download via magnet link")
            return False
        else:
            log("Private torrent with redacted hash and no URL - skipping")
            return False

    client = _get_client()
    try:
        client.auth_log_in()
    except qbittorrentapi.Forbidden403Error:
        log(
            "qBittorrent auth error: forbidden - this usually means qBittorrent has "
            "banned this IP after too many failed login attempts (Options > Web UI > "
            "\"Ban client after consecutive failures\"). Wait out the ban or clear it "
            "in qBittorrent's settings - a credential fix alone won't clear an active ban."
        )
        return False
    except qbittorrentapi.LoginFailed:
        log("qBittorrent auth error: login failed - check the configured username/password")
        return False
    except qbittorrentapi.APIConnectionError as e:
        log(f"qBittorrent auth error: could not connect - {e}")
        return False

    log("Authenticated with qBittorrent")

    magnet_link = f"magnet:?xt=urn:btih:{info_hash}"
    qb_category = sync_manager.get_qb_category()

    try:
        result = client.torrents_add(urls=magnet_link, category=qb_category or None)
    except qbittorrentapi.APIError as e:
        log(f"Failed to submit torrent: {e}")
        return False

    # Older qBittorrent (pre-API v2.14.0) replies with plain "Ok."/"Fails."
    # text; newer versions return structured metadata on success and raise
    # an exception (already handled above) on failure instead - so any
    # non-string result here already means success.
    if isinstance(result, str) and result.strip() != "Ok.":
        log(f"qBittorrent reported failure adding the torrent: {result!r}")
        return False

    category_msg = f" to category '{qb_category}'" if qb_category else ""
    log(f"Submitted magnet to qBittorrent{category_msg}: {magnet_link}")
    return True
