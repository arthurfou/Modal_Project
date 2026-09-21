"""Lyrics similarity graph: artists linked when the embeddings of their lyrics are close."""
import networkx as nx
import numpy as np
from pymongo import MongoClient
from sklearn.metrics.pairwise import cosine_similarity

from rap_graph.config import MONGO_URI
from rap_graph.graphs.common import plot_similarity_distribution
from rap_graph.tools import CLEAR_LINE, log

DEFAULT_MIN_COMPONENT_SIZE = 5


def build_graph(db_name, weighted=True, similarity_threshold=0.98, plot_distribution=True, **_):
    """
    Build the lyrics similarity graph from the artists that have an embedding.

    Two artists are linked if the cosine similarity of their embeddings is at least `similarity_threshold`.
    The edge weight rescales the similarity above the threshold: (similarity - threshold) * 50.
    """
    log(__file__, "Building graph...")
    client = MongoClient(MONGO_URI)
    artists = client[db_name]["artists"]

    graph = nx.Graph()
    id_to_embedding = {}
    for artist in artists.find({"embedding": {"$exists": True}}):
        log(__file__, f"Adding artist {artist['name']} to graph{CLEAR_LINE}", end="\r")
        artist_id = artist["id_genius"]
        graph.add_node(
            artist_id,
            name=str(artist["name"]),
            id_mongo=str(artist["_id"]),
            id_genius=int(artist_id),
            id_spotify=str(artist["id_spotify"]),
            url_genius=str(artist["url_genius"]),
            popularity=artist["popularity"],
            followers=artist["followers"],
        )
        id_to_embedding[artist_id] = np.array(artist["embedding"])
    client.close()
    log(__file__, f"All artists added to graph{CLEAR_LINE}")

    log(__file__, "Computing cosine similarities and adding edges...")
    artist_ids = list(id_to_embedding)
    similarity_matrix = cosine_similarity(np.array([id_to_embedding[aid] for aid in artist_ids]))
    scores = []
    for i in range(len(artist_ids)):
        for j in range(i + 1, len(artist_ids)):
            similarity = similarity_matrix[i][j]
            score = (similarity - similarity_threshold) * 50
            scores.append(score)
            if similarity >= similarity_threshold:
                if weighted:
                    graph.add_edge(artist_ids[i], artist_ids[j], weight=score)
                else:
                    graph.add_edge(artist_ids[i], artist_ids[j])
    log(__file__, f"Graph completed with {graph.number_of_edges()} similarity edges")

    if plot_distribution:
        plot_similarity_distribution(
            scores,
            title="Distribution of the rescaled cosine similarities between artists",
            xlabel="(cosine similarity - threshold) * 50",
        )

    return graph
