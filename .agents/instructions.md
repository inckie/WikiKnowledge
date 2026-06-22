# WikiKnowledge Agent Instructions

WikiKnowledge is a hierarchical knowledge graph construction system built over markdown files, utilizing FastAPI for the backend and plain JavaScript for the frontend.

The project contains an embedded knowledge base in the `knowledge/` directory, which holds both an in-depth overview of the system and detailed technical design documentation.

## Learning about the system
When connected, AI agents should use the project's own `wikiknowledge` MCP server tools (e.g., `get_article`, `list_articles`, `search`) to read and learn about the system from this embedded knowledge base. If the MCP server is not available, you should use standard file access tools as a fallback to read the markdown files directly from `knowledge/articles/` and `knowledge/categories/`.

## Updating the Knowledge Base (CRITICAL)
Whenever you implement changes, modify the architecture, or add new features to the WikiKnowledge codebase, **you must update the corresponding articles in the knowledge base.** Keeping this base up-to-date is a critical part of your workflow.

- We only need the **current, up-to-date status** of the system.
- Do NOT add changelogs, diffs, or walkthroughs of completed steps to the knowledge base. Simply modify the existing articles (or create new ones if necessary) so they accurately reflect the true current state of the system.
