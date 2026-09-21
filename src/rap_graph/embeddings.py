"""Artist embeddings: mean Word2Bezbar vector of the lyrics of their most popular songs."""
import re
import time
from functools import cache

import numpy as np

from rap_graph.config import WORD2BEZBAR_REPO, require_env
from rap_graph.sources import genius
from rap_graph.tools import CLEAR_LINE, log


@cache
def load_model():
    """Download (once, then cached by huggingface_hub) and load the Word2Bezbar model."""
    import gensim
    from huggingface_hub import snapshot_download

    model_dir = snapshot_download(WORD2BEZBAR_REPO, allow_patterns=["word2vec.model*"])
    return gensim.models.Word2Vec.load(f"{model_dir}/word2vec.model")


@cache
def _lyrics_client():
    import lyricsgenius

    client = lyricsgenius.Genius(require_env("GENIUS_ACCESS_TOKEN"))
    client.timeout = 10
    client.sleep_time = 0.1
    client.skip_non_songs = True
    client.excluded_terms = ["(Remix)", "(Live)"]
    client.remove_section_headers = True
    return client


def get_lyrics_from_genius(artist_name, max_songs=5):
    """Return the lyrics of the `max_songs` most popular songs of an artist on Genius (one string per song)."""
    try:
        artist = _lyrics_client().search_artist(artist_name, max_songs=max_songs, sort="popularity")
        if artist is None:
            log(__file__, f"No result for artist '{artist_name}'")
            return []

        lyrics_list = []
        for song in artist.songs[:max_songs]:
            if song.lyrics:
                lyrics_list.append(song.lyrics.strip())
            time.sleep(0.1)  # Avoid the rate limit
        return lyrics_list

    except Exception as e:
        log(__file__, f"Failed for {artist_name}: {e}")
        return []


def clean_lyrics(text, lowercase=True):
    """Clean raw Genius lyrics: remove section headers, parentheses, special characters and repeated lines."""
    # Remove sections between brackets ([Chorus], [Verse 1], [Intro]...)
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\n{2,}", "\n", text)
    # Remove metadata such as "(lyrics)", "(feat...)"
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"[^\w\s\'\-.,!?àâäéèêëîïôöùûüç]", "", text)

    # Remove repeated lines (ad-libs, choruses) so they do not bias the similarity
    unique_lines = []
    seen = set()
    for line in text.strip().split("\n"):
        clean_line = line.strip()
        if clean_line and clean_line not in seen:
            unique_lines.append(clean_line)
            seen.add(clean_line)
    text = "\n".join(unique_lines)

    if lowercase:
        text = text.lower()
    return text.strip()


def get_artist_vector(artist_id, model, max_songs=5):
    """Return the mean Word2Bezbar vector of the lyrics of a Genius artist, or None if it cannot be computed."""
    artist_name = genius.get_artist_name_by_id(artist_id)
    if artist_name is None:
        return None
    log(__file__, f"Processing {artist_name}{CLEAR_LINE}", end="\r")

    lyrics_list = get_lyrics_from_genius(artist_name, max_songs=max_songs)
    if not lyrics_list:
        log(__file__, f"[FAIL] No lyrics fetched for {artist_name}")
        return None
    log(__file__, f"{len(lyrics_list)} songs fetched for {artist_name}")

    tokens = clean_lyrics("\n".join(lyrics_list)).split()
    valid_tokens = [t for t in tokens if t in model.wv.key_to_index]
    if not valid_tokens:
        log(__file__, f"No token known by the model for {artist_name}")
        return None

    return np.mean([model.wv[t] for t in valid_tokens], axis=0)
