"""Clustering, statistics, cleaning and export functions shared by all the graphs."""
import os

import matplotlib.pyplot as plt
import networkx as nx

from rap_graph.config import GRAPHS_DIR
from rap_graph.tools import log

SEPARATOR = "-" * 52

CLUSTERING_METHODS = {
    "louvain": lambda graph, k: nx.community.louvain_communities(graph, seed=123),
    "k_clique": lambda graph, k: nx.community.k_clique_communities(graph, k),
    "label_propagation": lambda graph, k: nx.community.label_propagation_communities(graph),
    # girvan_newman yields successive partitions: keep the first one
    "girvan_newman": lambda graph, k: next(nx.community.girvan_newman(graph)),
    "greedy_modularity": lambda graph, k: nx.community.greedy_modularity_communities(graph),
}


def set_clusters(graph, method, k=3):
    """Detect communities with the given method and store their index in the `cluster` attribute of each node."""
    log(__file__, f"Setting clusters using {method}...")
    if method not in CLUSTERING_METHODS:
        raise ValueError(f"Unknown method: {method}")
    clusters = list(CLUSTERING_METHODS[method](graph, k))

    for i, cluster in enumerate(clusters):
        for node in cluster:
            graph.nodes[node]["cluster"] = i

    cluster_stats(clusters)
    return graph


def graph_stats(graph):
    log(__file__, "Graph stats:")
    print(f"Number of nodes: {graph.number_of_nodes()}")
    print(f"Number of edges: {graph.number_of_edges()}")
    print(f"Average degree: {sum(dict(graph.degree()).values()) / graph.number_of_nodes():.2f}")
    print(f"Density: {nx.density(graph):.4f}")
    print(f"Average clustering coefficient: {nx.average_clustering(graph):.4f}")
    print(f"Connected components: {nx.number_connected_components(graph)}")
    is_connected = nx.is_connected(graph)
    print(f"Is connected: {is_connected}")
    # Only defined on connected graphs
    if is_connected:
        print(f"Diameter: {nx.diameter(graph)}")
        print(f"Average shortest path length: {nx.average_shortest_path_length(graph):.2f}")
    log(__file__, SEPARATOR)


def cluster_stats(clusters):
    log(__file__, "Cluster stats:")
    print(f"Number of communities: {len(clusters)}")
    print("Number of nodes in each community:")
    for i, cluster in enumerate(clusters):
        print(f"  Community {i}: {len(cluster)} nodes")
    log(__file__, SEPARATOR)


def nodes_stats(graph, top=10):
    log(__file__, "Nodes stats:")
    centrality = nx.degree_centrality(graph)
    top_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:top]
    print("Top nodes by degree centrality:", [graph.nodes[node]["name"] for node, _ in top_nodes])
    log(__file__, SEPARATOR)


def delete_isolated_nodes(graph):
    isolated_nodes = list(nx.isolates(graph))
    graph.remove_nodes_from(isolated_nodes)
    log(__file__, f"Deleted {len(isolated_nodes)} isolated nodes")
    return graph


def delete_low_degree_nodes(graph, k, filename=None):
    """Delete the nodes with a degree strictly lower than k. If `filename` is given, save their names to it."""
    low_degree_nodes = [node for node, degree in graph.degree() if degree < k]
    if filename:
        with open(filename, "w", encoding="utf-8") as f:
            for node in low_degree_nodes:
                f.write(graph.nodes[node].get("name", str(node)) + "\n")
    graph.remove_nodes_from(low_degree_nodes)
    log(__file__, f"Deleted {len(low_degree_nodes)} nodes with degree < {k}")
    return graph


def delete_small_components(graph, min_size=10):
    """Delete the connected components with fewer than `min_size` nodes."""
    small_components = [c for c in nx.connected_components(graph) if len(c) < min_size]
    nodes_to_remove = set().union(*small_components)
    graph.remove_nodes_from(nodes_to_remove)
    log(__file__, f"Deleted {len(small_components)} components with less than {min_size} nodes "
                  f"({len(nodes_to_remove)} nodes removed)")
    return graph


def export_graph_to_gephi(graph, filename="graph.gexf"):
    """Export the graph to GEXF (readable by Gephi) in the graphs/ folder."""
    os.makedirs(GRAPHS_DIR, exist_ok=True)
    file_path = GRAPHS_DIR / filename
    nx.write_gexf(graph, file_path)
    log(__file__, f"Graph exported to {file_path}")


def plot_similarity_distribution(similarities, title, xlabel):
    plt.figure(figsize=(8, 5))
    plt.hist(similarities, bins=50, range=(0, 1), color="steelblue", edgecolor="black")
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel("Frequency")
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()
    plt.show()
