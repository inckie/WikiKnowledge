"""WikiKnowledge entry point.

Run with: python run.py
Or: uvicorn wikiknowledge.api.app:app --reload
"""

from wikiknowledge.api.app import main

if __name__ == "__main__":
    main()
