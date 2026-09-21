"""Collaboration graph: artists linked by the songs they made together."""
from itertools import combinations

import networkx as nx
from pymongo import MongoClient

from rap_graph.config import MONGO_URI
from rap_graph.tools import CLEAR_LINE, log

DEFAULT_MIN_COMPONENT_SIZE = 10


def build_graph(db_name, weighted=True, **_):
    """
    Build the collaboration graph from the `artists` and `featurings` collections.

    Nodes are Genius artist ids. Two artists are linked if they appear on the same song;
    if `weighted`, the edge weight is the number of songs they share.
    """
    log(__file__, "Building graph...")
    client = MongoClient(MONGO_URI)
    db = client[db_name]
    artists = db["artists"]
    featurings = db["featurings"]

    graph = nx.Graph()
    for artist in artists.find({}):
        log(__file__, f"Adding artist {artist['name']} to graph{CLEAR_LINE}", end="\r")
        graph.add_node(
            artist["id_genius"],
            name=str(artist["name"]),
            id_mongo=str(artist["_id"]),
            id_genius=int(artist["id_genius"]),
            pop=int(artist["popularity"]),
            followers=int(artist["followers"]),
            id_mb=str(artist["id_mb"]),
            id_spotify=str(artist["id_spotify"]),
            url_genius=str(artist["url_genius"]),
        )
    log(__file__, f"All artists added to graph{CLEAR_LINE}")

    log(__file__, f"Adding featurings to graph, {featurings.count_documents({})} featurings found")
    for featuring in featurings.find({}):
        for id_1, id_2 in combinations(featuring["artists_genius_id"], 2):
            if not graph.has_edge(id_1, id_2):
                graph.add_edge(id_1, id_2, weight=1)
            elif weighted:
                graph[id_1][id_2]["weight"] += 1
    log(__file__, f"All featurings added to graph: {graph.number_of_edges()} edges")

    client.close()
    return graph
