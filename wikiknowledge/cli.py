import argparse
import os
import uvicorn
from pathlib import Path

def main():
    """Run the server (entry point for pyproject.toml scripts)."""
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
    args, _ = parser.parse_known_args()

    if args.kb_dir:
        os.environ["WIKIKNOWLEDGE_KB_DIR"] = os.path.abspath(args.kb_dir)

    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    uvicorn.run(
        "wikiknowledge.api.app:app",
        host="0.0.0.0",
        port=args.port,
        reload=True,
        reload_dirs=[str(PROJECT_ROOT / "wikiknowledge")],
    )

if __name__ == "__main__":
    main()
