import argparse
import os
import uvicorn
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the server command line.

    Unknown arguments are ignored so the documented `main.py --port=8001
    serve-http` invocation keeps working.
    """
    parser = argparse.ArgumentParser(description="Run WikiKnowledge server.")
    parser.add_argument(
        "--kb-dir",
        type=str,
        help="Path to the knowledge base directory containing articles/ and categories/",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the server on",
    )
    parser.add_argument(
        "--no-reload",
        dest="reload",
        action="store_false",
        help=(
            "Disable auto-reload. For a background instance, where reloading on a "
            "source edit would drop every live MCP session attached to it."
        ),
    )
    parser.set_defaults(reload=True)
    args, _ = parser.parse_known_args(argv)
    return args


def main():
    """Run the server (entry point for pyproject.toml scripts)."""
    args = parse_args()

    if args.kb_dir:
        os.environ["WIKIKNOWLEDGE_KB_DIR"] = os.path.abspath(args.kb_dir)

    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    options = {"host": "0.0.0.0", "port": args.port, "reload": args.reload}
    if args.reload:
        options["reload_dirs"] = [str(PROJECT_ROOT / "wikiknowledge")]

    uvicorn.run("wikiknowledge.api.app:app", **options)


if __name__ == "__main__":
    main()
