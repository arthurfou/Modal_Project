"""Last.fm similarity graph: artists linked when Last.fm lists them as similar."""
import time

import networkx as nx
from pymongo import MongoClient

from rap_graph.config import MONGO_URI
from rap_graph.graphs.common import plot_similarity_distribution
from rap_graph.sources import lastfm
from rap_graph.tools import CLEAR_LINE, log

DEFAULT_MIN_COMPONENT_SIZE = 5


def build_graph(db_name, limit=20, plot_distribution=True, **_):
    """
    Build the Last.fm similarity graph.

    For each artist, the `limit` most similar artists on Last.fm are fetched; an edge is added
    when the similar artist is also in the database, weighted by the Last.fm match score.
    """
    client = MongoClient(MONGO_URI)
    all_artists = list(client[db_name]["artists"].find({}))
    client.close()

    graph = nx.Graph()
    name_to_artist = {}
    for artist in all_artists:
        graph.add_node(
            artist["id_genius"],
            name=artist["name"],
            id_mongo=str(artist["_id"]),
            id_genius=artist["id_genius"],
            id_spotify=str(artist["id_spotify"]),
            url_genius=str(artist["url_genius"]),
            popularity=artist.get("popularity"),
            followers=artist.get("followers"),
        )
        # Case insensitive matching of the Last.fm names
        name_to_artist[artist["name"].lower()] = artist

    similarities = []
    for i, artist in enumerate(all_artists, start=1):
        id_genius = artist["id_genius"]
        edges_before = graph.number_of_edges()

        try:
            similar = lastfm.get_similar_artists(artist["name"], limit=limit)["similarartists"]["artist"]
        except Exception as e:
            log(__file__, f"Error for {artist['name']}: {e}")
            continue

        for similar_artist in similar:
            similar_name = similar_artist["name"].strip().lower()
            if similar_name not in name_to_artist:
                continue
            target_id = name_to_artist[similar_name]["id_genius"]
            if not graph.has_edge(id_genius, target_id):
                score = float(similar_artist["match"])
                graph.add_edge(id_genius, target_id, weight=score)
                similarities.append(score)

        time.sleep(0.1)  # Respect the API rate limit
        log(__file__, f"Added {artist['name']} ({i}/{len(all_artists)}): "
                      f"{graph.number_of_edges() - edges_before} new edges.{CLEAR_LINE}", end="\r")

    log(__file__, f"Graph built with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges.")

    if plot_distribution:
        plot_similarity_distribution(
            similarities,
            title="Distribution of the Last.fm similarities between artists",
            xlabel="Last.fm similarity",
        )

    return graph
