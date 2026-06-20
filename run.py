"""Entry point for WikiKnowledge server."""

import uvicorn


def main():
    """Run the WikiKnowledge server."""
    uvicorn.run(
        "wikiknowledge.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["wikiknowledge"],
    )


if __name__ == "__main__":
    main()
