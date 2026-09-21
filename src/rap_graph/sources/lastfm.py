"""Last.fm API client."""
import requests

from rap_graph.config import require_env

API_URL = "http://ws.audioscrobbler.com/2.0/"


def get_similar_artists(artist_name, limit=20):
    """Return the raw Last.fm response of `artist.getsimilar` for an artist."""
    params = {
        "method": "artist.getsimilar",
        "artist": artist_name,
        "api_key": require_env("LASTFM_API_KEY"),
        "format": "json",
        "limit": limit,
    }
    response = requests.get(API_URL, params=params)
    response.raise_for_status()
    return response.json()
