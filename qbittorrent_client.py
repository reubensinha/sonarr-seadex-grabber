"""Client for interacting with qBittorrent API."""

import requests
from utils import log
from config import QB_URL, QB_USER, QB_PASS, QB_CATEGORY

session = requests.Session()


def qb_authenticate():
    """Authenticate with qBittorrent."""
    try:
        resp = session.post(
            f"{QB_URL}/api/v2/auth/login",
            data={"username": QB_USER, "password": QB_PASS},
        )
        if resp.text.strip() != "Ok.":
            raise Exception("qBittorrent login failed")
        log("Authenticated with qBittorrent")
    except Exception as e:
        log(f"qBittorrent auth error: {e}")


def send_to_qbittorrent(info_hash, is_private=False, torrent_url=None):
    """Send a torrent to qBittorrent using its info hash or URL for private torrents."""
    qb_authenticate()
    
    # Handle private torrents differently
    if is_private or info_hash == "<redacted>":
        if torrent_url:
            log(f"Private torrent detected - would need direct download from: {torrent_url}")
            log("Skipping private torrent - cannot download via magnet link")
            return
        else:
            log("Private torrent with redacted hash and no URL - skipping")
            return
    
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
    except requests.RequestException as e:
        log(f"Failed to submit torrent: {e}")
