"""MongoDB database: fetching artists and featurings from the APIs and storing them."""
import csv

from pymongo import MongoClient

from rap_graph import embeddings
from rap_graph.config import DATA_DIR, MONGO_URI
from rap_graph.sources import genius, musicbrainz, spotify
from rap_graph.tools import CLEAR_LINE, log

FAILED_ARTISTS_FILE = "failed_artists.txt"
MIN_FOLLOWERS = 1000


def _open_db(db_name):
    log(__file__, "Opening the MongoDB database...")
    client = MongoClient(MONGO_URI)
    return client, client[db_name]


def _search_new_artists(collection):
    """Fetch rap artists from Spotify and MusicBrainz, filter them and insert them in the collection."""
    log(__file__, "Fetching artists from Spotify...")
    new_artists = spotify.get_artists()
    log(__file__, f"Spotify fetching done. {len(new_artists)} artists fetched.")

    log(__file__, "Fetching artists from MusicBrainz...")
    musicbrainz_artists = musicbrainz.get_artists()
    log(__file__, f"MusicBrainz fetching done. {len(musicbrainz_artists)} artists fetched.")

    # Complete the MusicBrainz artists with their Spotify data, to get the same format
    log(__file__, "Standardising the artists format...")
    for artist in musicbrainz_artists:
        id_spotify, popularity, followers = spotify.get_artist_data(artist["name"])
        if id_spotify is not None:
            new_artists.append({
                "name": artist["name"],
                "id_spotify": id_spotify,
                "popularity": popularity,
                "followers": followers,
            })
    log(__file__, f"Online fetching done. {len(new_artists)} artists before filtering.")

    # Remove duplicates (case insensitive names) and artists with too few followers
    log(__file__, "Filtering the artists...")
    seen = set()
    filtered_artists = []
    for artist in new_artists:
        name = artist["name"].strip().lower()
        if name in seen:
            continue
        seen.add(name)
        followers = artist.get("followers")
        if followers is not None and followers >= MIN_FOLLOWERS:
            filtered_artists.append(artist)
    log(__file__, f"Filtering done. {len(filtered_artists)} artists kept.")

    with open("artists_list.txt", "w", encoding="utf-8") as f:
        for artist in filtered_artists:
            f.write(f"{artist['name']}\n")

    log(__file__, "Updating the database...")
    total = len(filtered_artists)
    for i, artist in enumerate(filtered_artists, start=1):
        log(__file__, f"[{i}/{total}] Updating artist: {artist['name']}{CLEAR_LINE}", end="\r")
        fields = {key: artist[key] for key in ("name", "id_spotify", "followers", "popularity")}
        collection.update_one(fields, {"$setOnInsert": fields}, upsert=True)
    log(__file__, f"Database update done. {total} artists updated.")


def update_artists(db_name, previous_db_name=None, search_new_artists=False, update_genius=False,
                   update_musicbrainz=False, update_embeddings=False):
    """
    Update the `artists` collection.

    - search_new_artists: fetch new artists from Spotify and MusicBrainz.
    - update_genius: find the Genius id and url of each artist. Artists not found are saved to FAILED_ARTISTS_FILE.
    - update_musicbrainz: find the MusicBrainz id of each artist.
    - update_embeddings: compute the lyrics embedding of each artist. If `previous_db_name` is given,
      embeddings already computed in that database are reused.
    """
    client, db = _open_db(db_name)
    collection = db["artists"]
    previous_collection = client[previous_db_name]["artists"] if previous_db_name else None

    if search_new_artists:
        _search_new_artists(collection)

    model = embeddings.load_model() if update_embeddings else None

    fails = []
    log(__file__, f"Updating the artists links...{CLEAR_LINE}")
    total = collection.count_documents({})
    for i, artist in enumerate(collection.find()):
        log(__file__, f"[{i}/{total}] Updating: {artist['name'].strip()}{CLEAR_LINE}", end="\r")

        if update_genius and "id_genius" not in artist:
            result = genius.get_artist_id_by_name(artist["name"])
            if result is None:
                log(__file__, f"Artist not found: {artist['name']}")
                fails.append(artist["name"])
                continue
            _, id_genius, url_genius = result
            collection.update_one({"name": artist["name"]}, {"$set": {"id_genius": id_genius, "url_genius": url_genius}})
            artist["id_genius"] = id_genius

        if update_embeddings and "id_genius" in artist and artist.get("embedding") is None:
            vector = None
            if previous_collection is not None:
                previous_artist = previous_collection.find_one({"id_genius": artist["id_genius"]})
                if previous_artist is not None:
                    vector = previous_artist.get("embedding")
            if vector is None:
                vector = embeddings.get_artist_vector(artist["id_genius"], model, max_songs=5)
            if vector is not None:
                if not isinstance(vector, list):
                    vector = vector.tolist()
                collection.update_one({"name": artist["name"]}, {"$set": {"embedding": vector}})

        if update_musicbrainz and "id_mb" not in artist:
            id_mb = musicbrainz.get_artist_id_by_name(artist["name"])
            if id_mb is not None:
                collection.update_one({"name": artist["name"]}, {"$set": {"id_mb": id_mb}})

    log(__file__, f"Number of artists in the database: {collection.count_documents({})}")

    log(__file__, f"Saving the artists not found to {FAILED_ARTISTS_FILE}...{CLEAR_LINE}")
    with open(FAILED_ARTISTS_FILE, "w", encoding="utf-8") as f:
        for name in fails:
            f.write(f"{name}\n")

    log(__file__, f"Closing the MongoDB database...{CLEAR_LINE}")
    client.close()


def retry_failed_artists(db_name, filename=FAILED_ARTISTS_FILE):
    """Interactively find the Genius id of the artists listed in `filename`, then rewrite it with the remaining ones."""
    client, db = _open_db(db_name)
    collection = db["artists"]

    with open(filename, "r", encoding="utf-8") as f:
        fails = [line.strip() for line in f if line.strip()]
    total = len(fails)
    log(__file__, f"{total} failed artists read from {filename}")

    remaining = []
    for i, name in enumerate(fails, start=1):
        log(__file__, f"[{i}/{total}] Updating artist: {name}")
        result = genius.get_artist_id_by_name_manual()
        if result is None:
            log(__file__, f"{name} not updated")
            remaining.append(name)
            continue
        _, id_genius, url_genius = result
        collection.update_one({"name": name}, {"$set": {"id_genius": id_genius, "url_genius": url_genius}})

    client.close()
    log(__file__, f"Saving the {len(remaining)} remaining failed artists to {filename}...")
    with open(filename, "w", encoding="utf-8") as f:
        for name in remaining:
            f.write(f"{name}\n")


def import_artists_csv(db_name, filename=DATA_DIR / "db_artists_clean.csv"):
    """Replace the `artists` collection with the artists of a CSV file."""
    client, db = _open_db(db_name)
    collection = db["artists"]
    collection.delete_many({})

    log(__file__, f"Reading {filename}...")
    with open(filename, newline="", encoding="utf-8") as csvfile:
        for row in csv.DictReader(csvfile):
            collection.insert_one({
                "name": row["name"],
                "id_spotify": row["id_spotify"],
                "followers": int(row["followers"]),
                "popularity": int(row["popularity"]),
                "id_genius": int(row["id_genius"]),
                "url_genius": row["url_genius"],
                "id_mb": row.get("id_mb"),
            })
    log(__file__, f"{collection.count_documents({})} artists imported.")
    client.close()


def update_featurings(db_name, max_pages=60):
    """
    Fill the `featurings` collection with the songs of each artist that involve at least
    two artists of the `artists` collection.
    """
    client, db = _open_db(db_name)
    artists_col = db["artists"]
    featurings_col = db["featurings"]

    fails = []
    all_artists = list(artists_col.find({}))
    total = len(all_artists)
    for i, artist in enumerate(all_artists):
        log(__file__, f"[{i}/{total}] Processing artist: {artist['name']}{CLEAR_LINE}", end="\r")

        try:
            tracks = genius.get_artist_featurings(artist["id_genius"], max_pages=max_pages)
        except Exception as e:
            log(__file__, f"Error for {artist['name']}: {e}")
            fails.append(artist["name"])
            continue

        for song_id, title, authors_id in tracks:
            matched_names = []
            matched_ids = []
            matched_genius_ids = []
            for author_id in authors_id:
                matched = artists_col.find_one({"id_genius": int(author_id)})
                if matched is not None:
                    matched_names.append(matched["name"])
                    matched_ids.append(matched["_id"])
                    matched_genius_ids.append(matched["id_genius"])

            if len(matched_ids) >= 2:
                featurings_col.update_one(
                    {"_id": song_id},
                    {"$setOnInsert": {
                        "_id": int(song_id),
                        "title": title,
                        "artists_id": matched_ids,
                        "artists_names": matched_names,
                        "artists_genius_id": matched_genius_ids,
                    }},
                    upsert=True,
                )

    if fails:
        log(__file__, f"Featurings could not be fetched for: {', '.join(fails)}")
    log(__file__, f"{featurings_col.count_documents({})} featurings in the database.")
    client.close()
