import argparse
import sys

from rag import pipeline


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rag")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Ingest documents into the store")
    ingest_parser.add_argument("--data-dir", default=None, help="Directory of documents to ingest")

    query_parser = subparsers.add_parser("query", help="Ask a question over ingested documents")
    query_parser.add_argument("question", help="Question to ask")
    query_parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        help="Number of chunks to retrieve (default: auto, via category-adaptive recall depth)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        if args.command == "ingest":
            count = pipeline.ingest(data_dir=args.data_dir)
            print(f"Ingested {count} chunks.")
        elif args.command == "query":
            result = pipeline.query(args.question, top_k=args.top_k)
            print(result["answer"])
            print("\nSources:")
            for source in result["sources"]:
                print(f"  - {source}")
    except (FileNotFoundError, ConnectionError) as e:
        print(str(e), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
