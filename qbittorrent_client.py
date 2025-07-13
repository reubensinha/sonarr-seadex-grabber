"""Client for interacting with qBittorrent API."""

import requests
from utils import log
from config import QB_URL, QB_USER, QB_PASS

session = requests.Session()


def qb_authenticate():
    """Authenticate with qBittorrent."""
    try:
        resp = session.post(f"{QB_URL}/api/v2/auth/login", data={
            "username": QB_USER,
            "password": QB_PASS
        })
        if resp.text.strip() != "Ok.":
            raise Exception("qBittorrent login failed")
        log("Authenticated with qBittorrent")
    except Exception as e:
        log(f"qBittorrent auth error: {e}")


def send_to_qbittorrent(info_hash):
    """Send a torrent to qBittorrent using its info hash."""
    qb_authenticate()
    magnet_link = f"magnet:?xt=urn:btih:{info_hash}"
    try:
        resp = session.post(f"{QB_URL}/api/v2/torrents/add", data={"urls": magnet_link})
        resp.raise_for_status()
        log(f"Submitted magnet to qBittorrent: {magnet_link}")
    except requests.RequestException as e:
        log(f"Failed to submit torrent: {e}")
