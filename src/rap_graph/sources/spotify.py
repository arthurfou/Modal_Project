"""Spotify Web API client (client credentials flow)."""
import time

import requests

from rap_graph.config import require_env
from rap_graph.tools import CLEAR_LINE, log

API_URL = "https://api.spotify.com/v1"
TOKEN_URL = "https://accounts.spotify.com/api/token"

DEFAULT_GENRES = ["french rap"]

_token = None
_token_expiry = 0.0


def _headers():
    """Return the authorization headers, requesting a new access token when needed."""
    global _token, _token_expiry
    if _token is None or time.time() >= _token_expiry:
        response = requests.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(require_env("SPOTIFY_CLIENT_ID"), require_env("SPOTIFY_CLIENT_SECRET")),
        )
        response.raise_for_status()
        payload = response.json()
        _token = payload["access_token"]
        _token_expiry = time.time() + payload.get("expires_in", 3600) - 60
    return {"Authorization": f"Bearer {_token}"}


def get_artists(genres=DEFAULT_GENRES):
    """Return the artists tagged with the given genres (name, Spotify id, popularity, followers)."""
    artists = []
    for genre in genres:
        log(__file__, f"Fetching artists of genre: {genre}")
        for offset in range(0, 1000, 50):
            # Avoid spamming the API
            time.sleep(0.5)

            log(__file__, f"Artists processed: {offset}, fetching the next 50", end="\r")
            params = {"q": f'genre:"{genre}"', "type": "artist", "limit": 50, "offset": offset}
            response = requests.get(f"{API_URL}/search", headers=_headers(), params=params)
            items = response.json()["artists"]["items"]
            if not items:
                break
            for artist in items:
                artists.append({
                    "name": artist["name"],
                    "id_spotify": artist["id"],
                    "popularity": artist["popularity"],
                    "followers": artist["followers"]["total"],
                })
    log(__file__, f"Fetching done{CLEAR_LINE}")
    return artists


def get_artist_data(artist_name):
    """Return the Spotify id, popularity and number of followers of an artist from its name."""
    params = {"q": artist_name, "type": "artist", "limit": 1}
    response = requests.get(f"{API_URL}/search", headers=_headers(), params=params)
    items = response.json().get("artists", {}).get("items", [])
    if not items:
        return None, None, None
    artist = items[0]
    return artist.get("id"), artist.get("popularity"), artist.get("followers", {}).get("total")


def get_popularity(artist_id):
    """Return the popularity and number of followers of an artist from its Spotify id."""
    response = requests.get(f"{API_URL}/artists/{artist_id}", headers=_headers())
    results = response.json()
    popularity = results.get("popularity")
    followers = results.get("followers", {}).get("total")
    return popularity, followers
