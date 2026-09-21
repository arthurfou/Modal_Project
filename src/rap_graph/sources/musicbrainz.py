"""MusicBrainz client (through the musicbrainzngs library and the raw web service)."""
import string
import time

import musicbrainzngs
import requests

from rap_graph.tools import log

USER_AGENT = ("RapCollabParser", "1.0", "contact@example.org")
API_URL = "https://musicbrainz.org/ws/2"
HEADERS = {"User-Agent": f"{USER_AGENT[0]}/{USER_AGENT[1]} ( {USER_AGENT[2]} )"}

musicbrainzngs.set_useragent(*USER_AGENT)


def get_artist_id_by_name(name):
    """Return the MusicBrainz id of the best match for an artist name, or None."""
    try:
        result = musicbrainzngs.search_artists(artist=name, limit=1)
        if result["artist-count"] > 0:
            return result["artist-list"][0]["id"]
        return None
    except Exception as e:
        log(__file__, f"MusicBrainz error for {name}: {e}")
        return None


def get_artists():
    """Return the French and Belgian rap artists listed on MusicBrainz, querying one initial letter at a time."""
    all_artists = []

    for letter in string.ascii_lowercase:
        query = (
            f'artist:{letter}* AND (tag:"rap" OR tag:"hip hop" OR tag:"trap" OR "cloud rap" ) '
            "AND (country:FR OR country:BE)"
        )
        params = {"query": query, "fmt": "json", "limit": 100}

        response = requests.get(f"{API_URL}/artist", params=params, headers=HEADERS)
        time.sleep(0.5)
        response.raise_for_status()
        results = response.json().get("artists", [])

        for i, artist in enumerate(results):
            if artist.get("name"):
                all_artists.append({"name": artist["name"]})
                log(__file__, f"{i + 1} / {len(results)} artists fetched for letter {letter.upper()}", end="\r")

    return all_artists
