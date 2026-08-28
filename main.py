#!/usr/bin/env python
"""WikiKnowledge entry point.

Run with: python run.py
Or: uvicorn wikiknowledge.api.app:app --reload
"""

from wikiknowledge.cli import main

if __name__ == "__main__":
    main()
