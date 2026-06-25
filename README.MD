# WikiKnowledge Graph Construction and Question Answering System

WikiKnowledge is designed to solve the problem of "fragmented" knowledge by building a hierarchical, fractal knowledge graph. Unlike Wikipedia, which can be difficult to follow as a structured educational path, WikiKnowledge uses "overview" articles (category articles) to provide summary-driven pathways through different layers of information. Combination of the hierarchical structure and wiki tools allows users and AIs to easily navigate through the knowledge graph, while also providing a clear overview of the relationships between different topics.

See [knowledge/articles/overview.md](knowledge/articles/overview.md) for the overview of the project.

TODO:

- [ ] fix get_category_status tool
- [ ] add frontend-looking MCP tools for Chat agent specifically (check current article, help user modify it, suggest new categories or articles, etc.). Probably can be done by sending "context" to backend
- [ ] binary files support (images). Each item will have .meta file next to it
- [ ] multiple knowledge bases on one server
- [ ] readonly mode
- [ ] implement the dirty articles update cascading with AI
- [ ] add MongoDB/SQLite support for storing the knowledge graph
- [ ] implement purgeable index cache in `knowledge/.index`
- [ ] implement authentication
- [ ] provide response techical details in chat when possible (token count, t/s)
