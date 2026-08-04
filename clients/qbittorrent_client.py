"""Client for interacting with qBittorrent API."""

import requests
from core.utils import log
from core.config import QB_URL, QB_USER, QB_PASS, QB_CATEGORY

session = requests.Session()


def qb_authenticate() -> bool:
    """Authenticate with qBittorrent. Returns True on success, False otherwise."""
    try:
        resp = session.post(
            f"{QB_URL}/api/v2/auth/login",
            data={"username": QB_USER, "password": QB_PASS},
        )
        if resp.text.strip() != "Ok.":
            log("qBittorrent auth error: login failed (unexpected response)")
            return False
        log("Authenticated with qBittorrent")
        return True
    except Exception as e:
        log(f"qBittorrent auth error: {e}")
        return False


def send_to_qbittorrent(info_hash, is_private=False, torrent_url=None) -> bool:
    """Send a torrent to qBittorrent using its info hash or URL for private torrents.

    Returns True only if the torrent was actually submitted successfully.
    """
    if not qb_authenticate():
        log("Skipping submission - qBittorrent authentication failed")
        return False

    # Handle private torrents differently
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

    magnet_link = f"magnet:?xt=urn:btih:{info_hash}"

    # Prepare data for torrent submission
    data = {"urls": magnet_link}

    # Add category if configured
    if QB_CATEGORY:
        data["category"] = QB_CATEGORY

    try:
        resp = session.post(f"{QB_URL}/api/v2/torrents/add", data=data)
        resp.raise_for_status()

        category_msg = f" to category '{QB_CATEGORY}'" if QB_CATEGORY else ""
        log(f"Submitted magnet to qBittorrent{category_msg}: {magnet_link}")
        return True
    except requests.RequestException as e:
        log(f"Failed to submit torrent: {e}")
        return False
