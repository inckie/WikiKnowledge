---
categories:
- ai-integration
created: '2026-06-21T10:10:00+00:00'
id: ai-interaction-guide
modified: '2026-06-24T02:24:47.009421+00:00'
tags:
- ai
- mcp
- guide
- best-practices
title: AI Interaction Guide for WikiKnowledge
type: leaf
---

# AI Interaction Guide for WikiKnowledge

This guide provides essential information for AI agents interacting with a WikiKnowledge base via the Model Context Protocol (MCP).

## System Overview

WikiKnowledge is a system for building a structured knowledge graph from markdown articles. The core idea is to organize information hierarchically, allowing users (and AIs) to explore topics from a high-level overview down to specific details. This structure avoids the need to process large, unstructured documents, saving context space and enabling efficient information retrieval.

## Knowledge Structure

The knowledge base consists of two types of articles:
1.  **Leaf Articles**: Contain specific, detailed information on a single topic.
2.  **Category Articles**: Provide high-level summaries of a topic area, linking to relevant leaf articles and other categories.

These articles are interconnected using three primary mechanisms:
*   **Wiki Links (`[[article-id]]`)**: Direct links between articles, forming a web of knowledge.
*   **Categories**: A formal hierarchy where leaf articles are grouped under one or more category articles.
*   **Tags**: Freeform labels for ad-hoc classification and discovery.

This structure allows you to navigate the knowledge graph efficiently. Instead of "reading" entire documents, you can traverse categories, follow wiki links, and filter by tags to pinpoint the exact information you need.

## Using MCP Tools for Information Discovery

Your primary interface to the knowledge base is through MCP tools. Use them to explore the graph before adding new information.

### Key Tools and Workflow

1.  **`list_articles()`**: Start here to get a sense of the existing knowledge.
    *   **`list_articles(article_type='category')`**: Crucial first step. See all available categories to understand the main topic areas.
    *   **`list_articles(tag='some-tag')`**: Find articles related to a specific concept.

2.  **`get_article(article_id)`**: Once you identify a relevant category or article, retrieve its content.
    *   If it's a category, read its summary to understand its scope.
    *   Pay attention to the `tags` and `categories` in the frontmatter.

3.  **`get_category_members(category_id)`**: See all articles belonging to a specific category.

4.  **`get_category_status(category_id)`**: Check if a category's summary is outdated ("dirty"). Use this before summarizing categories or during maintenance to identify which category articles need their AI-generated summaries updated.

5.  **`get_backlinks(article_id)`**: Discover which other articles reference the current one. This is a powerful tool for understanding context and relationships.

6.  **`search(query)`**: Use for broad, full-text searches when you don't know where to start.

7.  **`list_resources()` / `get_resource(resource_id)`**: Discover what images, diagrams, or other binary files are already uploaded in the knowledge base and retrieve their metadata or content.

8.  **`upload_resource(...)` / `delete_resource(resource_id)`**: Upload or delete media resources.

## Adding and Updating Knowledge

When adding new information, your goal is to integrate it cleanly into the existing graph.

### Workflow for Adding a New Leaf Article

1.  **Explore First**: Before creating a new article, use the discovery tools (`list_articles`, `search`) to ensure the information doesn't already exist.

2.  **Check Categories**: Use **`list_articles(article_type='category')`** to find suitable categories for your new article.
    *   Read the summaries of potentially relevant categories with **`get_article()`**.
    *   **Decision**: Does a fitting category exist?
        *   **Yes**: Use the existing category ID in your new article's frontmatter.
        *   **No**: You may need to create a new category. See the section below.

3.  **Identify Tags**: Use **`get_all_tags()`** to see existing tags. Reuse existing tags where possible to maintain consistency.

4.  **Create the Article**: Use the **`save_article()`** tool with `article_type='leaf'`.

### Workflow for Managing and Embedding Media Files

When an article requires images, diagrams, logos, or other binary files:

1.  **Check Existing**: Run **`list_resources()`** to see if the file is already uploaded.
2.  **Upload/Update**: If not, use the **`upload_resource()`** tool.
    *   **Resource ID**: Ensure the `resource_id` explicitly retains the file extension (e.g., `id: diagram.png`) to avoid name collisions and ensure clarity.
    *   **Description**: Provide a rich, descriptive summary of the media's content in the `description` parameter. This is critical for text-only LLMs accessing the knowledge base to understand the image or graphic.
    *   **Related**: Link the resource to the parent article using the `related` field to establish the connection in the graph.
3.  **Embed**: Reference the uploaded resource in your article's markdown using: `[[file:resource-id.ext|optional display caption]]`. For images, this renders as a structured `<figure>` inline; for non-image files, it renders as a download link.

### Workflow for Creating a Category Article

A category acts as a summary and entry point for a topic. Create one when you identify a new, distinct cluster of knowledge.

1.  **Justification**: Have you identified several existing or planned leaf articles that belong together but don't fit well into an existing category? If yes, a new category is appropriate.

2.  **Create the Category Article**: Use the **`save_article()`** tool with `article_type='category'`. The `content` you provide is crucial. It must be a string that includes a human-written introduction and an empty AI block for the system to populate.

    **Example `content` for a new category:**

```
<!-- human:start -->
This is the human-written introduction. It defines the scope and importance of the category.
<!-- human:end -->

## Articles in This Category

<!-- ai:start -->
This is AI written overview of the topic and list of the subcategories and leaf articles with brief description for each.
<!-- ai:end -->
```

When you use `save_article`, pass this markdown text as the `content` parameter.

### Example: Adding a "Collision Detection" Leaf Article

1.  **Search**: `search('collision detection')` returns no specific article.
2.  **Explore Categories**: `list_articles(article_type='category')` shows `physics-simulation`.
3.  **Analyze Category**: `get_article('physics-simulation')` confirms it's the right place.
4.  **Check Tags**: `get_all_tags()` shows relevant tags like `physics` and `simulation`.
5.  **Save Article**:
    ```python
    save_article(
        article_id='collision-detection',
        title='Collision Detection Algorithms',
        article_type='leaf',
        categories=['physics-simulation'],
        tags=['physics', 'simulation', 'collision-detection'],
        content='This article describes the GJK and SAT algorithms for [[rigid-body-dynamics|rigid body]] collision detection...'
    )
    ```

By following these steps, you contribute to the knowledge base in a structured way, enhancing its value and navigability for all users and AIs.