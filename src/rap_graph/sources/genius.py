"""Genius API client (artist search and featurings)."""
import requests

from rap_graph.config import require_env
from rap_graph.tools import int_response, log

API_URL = "https://api.genius.com"

# Suffixes appended to the search query when an artist cannot be found by its name alone
SEARCH_SUFFIXES = ["fr"]


def _headers():
    return {"Authorization": f"Bearer {require_env('GENIUS_ACCESS_TOKEN')}"}


def _search(query):
    """Return the hits of a Genius search, or None if the request failed."""
    response = requests.get(f"{API_URL}/search", headers=_headers(), params={"q": query})
    if response.status_code != 200:
        log(__file__, f"Error: {response.status_code}")
        return None
    return response.json()["response"]["hits"]


def get_artist_id_by_name(artist_name, suffix=None):
    """
    Look for an artist on Genius whose name matches `artist_name` (case insensitive).

    If no exact match is found, the search is retried with each suffix of SEARCH_SUFFIXES.
    Returns (name, id, url) or None.
    """
    if suffix is None:
        query = artist_name
    else:
        log(__file__, f"Searching {artist_name} with suffix '{suffix}' -> ", end="")
        query = f"{artist_name} {suffix}"

    hits = _search(query)
    if hits is None:
        return None
    if not hits:
        log(__file__, "No result found.")
        return None

    artist = None
    for hit in hits:
        genius_name = hit["result"]["primary_artist"]["name"].replace("’", "'")
        if genius_name.lower() == artist_name.lower().strip():
            artist = hit["result"]["primary_artist"]
            break

    if artist is None:
        if suffix is None:
            for next_suffix in SEARCH_SUFFIXES:
                result = get_artist_id_by_name(artist_name, suffix=next_suffix)
                if result is not None:
                    return result
        else:
            print("no artist found.")
        return None
    if suffix is not None:
        print("artist found.")

    return artist["name"], artist["id"], artist["url"]


def get_artist_id_by_name_manual():
    """
    Interactively search for an artist: the user types queries and picks the right artist among the results.

    Returns (name, id, url), or None if the user quits (by typing 0).
    """
    while True:
        query = input("[genius.py] (type 0 to quit) Query: ")
        if query == "0":
            return None

        hits = _search(query)
        if hits is None:
            return None
        if not hits:
            log(__file__, "No result found.")
            return None

        for i, hit in enumerate(hits):
            artist = hit["result"]["primary_artist"]
            print(f"[{i}] Name: {artist['name']}, ID: {artist['id']}, URL: {artist['url']}")

        choice = int_response("Pick the matching artist, otherwise type any other number: ")
        if 0 <= choice < len(hits):
            artist = hits[choice]["result"]["primary_artist"]
            break
        log(__file__, "No result selected.")

    log(__file__, f"Selected artist [{choice}] Name: {artist['name']}, ID: {artist['id']}, URL: {artist['url']}")
    return artist["name"], artist["id"], artist["url"]


def get_artist_name_by_id(artist_id):
    """Return the name of a Genius artist from its id, or None."""
    response = requests.get(f"{API_URL}/artists/{artist_id}", headers=_headers())
    if response.status_code != 200:
        log(__file__, f"Error: {response.status_code}")
        return None
    return response.json()["response"]["artist"]["name"]


def get_artist_featurings(artist_id, max_pages=1):
    """
    Return the songs of an artist that involve at least two artists.

    Each song is a tuple (song_id, title, [genius ids of the primary and featured artists]).
    """
    songs = []
    for page in range(1, max_pages + 1):
        params = {"page": page, "sort": "popularity"}
        response = requests.get(f"{API_URL}/artists/{artist_id}/songs", headers=_headers(), params=params)
        if response.status_code != 200:
            log(__file__, f"Error on page {page}: {response.status_code}")
            break

        song_list = response.json().get("response", {}).get("songs", [])
        if not song_list:
            break

        for song in song_list:
            primary_artist_id = song.get("primary_artist", {}).get("id")
            featured_artists = song.get("featured_artists", [])
            authors_id = [primary_artist_id] + [artist["id"] for artist in featured_artists]
            if len(authors_id) > 1:
                songs.append((song.get("id"), song.get("title"), authors_id))

    return songs
