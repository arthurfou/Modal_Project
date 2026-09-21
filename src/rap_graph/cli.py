"""Command line interface: `rap-graph <command>`."""
import argparse
import importlib

from rap_graph.config import DATA_DIR, MONGO_DB

GRAPH_TYPES = ["collab", "embedding", "lastfm"]


def _fetch_artists(args):
    from rap_graph import db

    db.update_artists(
        args.db,
        previous_db_name=args.previous_db,
        search_new_artists=args.search_new,
        update_genius=args.genius,
        update_musicbrainz=args.musicbrainz,
        update_embeddings=args.embeddings,
    )


def _retry_failed(args):
    from rap_graph import db

    db.retry_failed_artists(args.db, filename=args.file)


def _import_artists_csv(args):
    from rap_graph import db

    db.import_artists_csv(args.db, filename=args.file)


def _import_featurings_csv(args):
    from rap_graph import db

    db.import_featurings_csv(args.db, filename=args.file)


def _fetch_featurings(args):
    from rap_graph import db

    db.update_featurings(args.db, max_pages=args.max_pages)


def _build_graph(args):
    from rap_graph.graphs import common

    builder = importlib.import_module(f"rap_graph.graphs.{args.type}")
    graph = builder.build_graph(args.db, plot_distribution=not args.no_plot)

    min_size = args.min_component if args.min_component is not None else builder.DEFAULT_MIN_COMPONENT_SIZE
    graph = common.delete_small_components(graph, min_size)

    common.graph_stats(graph)
    common.nodes_stats(graph)

    graph = common.set_clusters(graph, args.method, k=args.k)
    common.export_graph_to_gephi(graph, filename=args.output or f"{args.type}_{args.method}_new.gexf")


def main():
    parser = argparse.ArgumentParser(prog="rap-graph", description=__doc__)
    parser.add_argument("--db", default=MONGO_DB, help=f"MongoDB database name (default: {MONGO_DB})")
    commands = parser.add_subparsers(dest="command", required=True)

    fetch = commands.add_parser("fetch-artists", help="Fetch or complete the artists from the APIs")
    fetch.add_argument("--search-new", action="store_true", help="Search new artists on Spotify and MusicBrainz")
    fetch.add_argument("--genius", action="store_true", help="Find the Genius id of each artist")
    fetch.add_argument("--musicbrainz", action="store_true", help="Find the MusicBrainz id of each artist")
    fetch.add_argument("--embeddings", action="store_true", help="Compute the lyrics embedding of each artist")
    fetch.add_argument("--previous-db", help="Database to reuse already computed embeddings from")
    fetch.set_defaults(func=_fetch_artists)

    retry = commands.add_parser("retry-failed", help="Interactively find the Genius id of the artists not found")
    retry.add_argument("--file", default="failed_artists.txt")
    retry.set_defaults(func=_retry_failed)

    import_csv = commands.add_parser(
        "import-artists-csv", help="Replace the artists collection with the artists of a CSV file"
    )
    import_csv.add_argument("--file", default=DATA_DIR / "artists.csv", help="CSV file (default: data/artists.csv)")
    import_csv.set_defaults(func=_import_artists_csv)

    import_feats = commands.add_parser(
        "import-featurings-csv", help="Replace the featurings collection with the songs of a CSV file"
    )
    import_feats.add_argument("--file", default=DATA_DIR / "featurings.csv",
                              help="CSV file (default: data/featurings.csv)")
    import_feats.set_defaults(func=_import_featurings_csv)

    featurings = commands.add_parser("fetch-featurings", help="Fetch the featurings between the artists from Genius")
    featurings.add_argument("--max-pages", type=int, default=60, help="Genius song pages per artist (default: 60)")
    featurings.set_defaults(func=_fetch_featurings)

    build = commands.add_parser("build-graph", help="Build, cluster and export a graph to graphs/ (GEXF)")
    build.add_argument("type", choices=GRAPH_TYPES)
    build.add_argument("--method", default="louvain",
                       choices=["louvain", "k_clique", "label_propagation", "girvan_newman", "greedy_modularity"])
    build.add_argument("--k", type=int, default=3, help="Clique size for k_clique (default: 3)")
    build.add_argument("--min-component", type=int,
                       help="Delete connected components smaller than this (default: 10 for collab, 5 otherwise)")
    build.add_argument("--no-plot", action="store_true", help="Do not plot the similarity distribution")
    build.add_argument("--output", help="Output file name (default: <type>_<method>_new.gexf)")
    build.set_defaults(func=_build_graph)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
