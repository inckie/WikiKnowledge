# WikiKnowledge Graph Construction and Question Answering System

WikiKnowledge is designed to solve the problem of "fragmented" knowledge by building a hierarchical, fractal knowledge graph. Unlike Wikipedia, which can be difficult to follow as a structured educational path, WikiKnowledge uses "overview" articles (category articles) to provide summary-driven pathways through different layers of information. Combination of the hierarchical structure and wiki tools allows users and AIs to easily navigate through the knowledge graph, while also providing a clear overview of the relationships between different topics.

See [knowledge/articles/overview.md](knowledge/articles/overview.md) for the overview of the project.

TODO:

- [ ] connect AI model to the project and implement the update cascading
- [ ] add what links there for category articles (both "parents" and "children")
- [ ] 'dirty' flag for categories: when an article is updated, mark all categories it belongs to as 'dirty' and in need of updating recursively. Probably will be enough to keep timestamp of last seen article change and compare to last update of articles in the category. Category will also be considered dirty if any articles that belong to the category but have been created since the last category last update.
- [ ] add MongoDB support for storing the knowledge graph
- [ ] implement purgeable index cache in `knowledge/.index`
- [ ] implement question answering system
- [ ] implement authentication
