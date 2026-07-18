---
categories:
- user-manual
created: '2026-06-21T10:10:00+00:00'
id: ai-interaction-guide
modified: '2026-07-18T06:32:36.470682+00:00'
tags:
- ai
- mcp
- guide
- best-practices
- skill
title: AI Interaction Guide for WikiKnowledge
type: leaf
---

# AI Interaction Guide for WikiKnowledge

This guide provides essential information for AI agents interacting with a WikiKnowledge base via the Model Context Protocol (MCP).

> [!IMPORTANT]
> **Foundational Rules**: Before you attempt to format frontmatter, create wiki links, or write category articles, you MUST read the [[markup-conventions]] category. It contains the strict syntax rules required for your edits to be parsed correctly by the system. Do not guess the syntax.

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

### Workflow for Updating an Existing Article

When you need to make partial updates to an existing article, avoid using `save_article` as it requires sending the entire content back, which is inefficient and risks data loss for large articles.
Instead, use the **`update_article()`** tool.

> [!WARNING]
> **The Frontmatter Trap:** `get_article()` returns the *entire raw markdown file*, including the YAML frontmatter block at the top. However, when using `save_article()` or `update_article()`, the `content` parameter must be **only the markdown body** (excluding the YAML frontmatter). Do not pass the frontmatter text into the `content` parameter, as it will erroneously embed a metadata block inside the article body. Pass metadata using their dedicated parameters instead (`tags`, `categories`, `title`, etc.).

1.  **Metadata Updates**: You can provide partial metadata (`title`, `tags`, etc.) to update just those fields.
2.  **Content Updates (diff-match-patch)**: To modify parts of the content, provide a `content_patches` argument formatted as a standard [diff-match-patch](https://github.com/google/diff-match-patch) patch string. This allows for safe, localized text replacements without overwriting the entire file.
3.  **Full Content Replacement**: If generating patches is too complex or the entire content needs rewriting, you can pass the full markdown text via the `content` argument (which will override `content_patches`).

### Workflow for Moving or Renaming an Article

If an article's ID needs to change (e.g., to better reflect its content or fix a typo), do **not** try to delete and recreate it. Instead, use the **`move_article()`** tool.

This tool is critical because it will automatically find all incoming `[[wiki-links]]` across the entire knowledge base and update them to point to the new ID, preserving the integrity of the graph.

### Workflow for Managing and Embedding Media Files

When an article requires images, diagrams, logos, or other binary files:

1.  **Check Existing**: Run **`list_resources()`** to see if the file is already uploaded.
2.  **Upload/Update**: If not, use the **`upload_resource()`** tool.
    *   **Resource ID**: Ensure the `resource_id` explicitly retains the file extension (e.g., `id: diagram.png`) to avoid name collisions and ensure clarity.
    *   **Description**: Provide a rich, descriptive summary of the media's content in the `description` parameter. This is critical for text-only LLMs accessing the knowledge base to understand the image or graphic.
    *   **Related**: Link the resource to the parent article using the `related` field to establish the connection in the graph.
3.  **Embed**: Reference the uploaded resource in your article's markdown using: `[[file:resource-id.ext|optional display caption]]`. For images, this renders as a structured `<figure>` inline; for non-image files, it renders as a download link.

### Workflow for Embedding Diagrams with Mermaid

When an article requires flowcharts, sequence diagrams, state diagrams, or other structural visuals that can be expressed as code, prefer using inline Mermaid diagrams over uploading static images:

1.  Create a standard fenced code block specifying `mermaid` as the language:
    ```markdown
    ` ``mermaid
    graph TD
        A[Start] --> B[Process];
    ` ``
    ```
    *(Note: remove the space between backticks when using)*
2.  The frontend automatically intercepts and renders these blocks seamlessly.
3.  This is highly recommended for AIs because it allows for easy future modification and version control compared to static binary images.

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

### Workflow for Updating a Dirty Category Article

When a leaf article is created or modified, its parent categories become "dirty" because their AI-generated summaries are out of date. **As an AI agent, it is your responsibility to manually rewrite and update this summary block.** 

Follow this exact process to update a dirty category:

1.  **Identify**: Use `get_category_status(category_id)` to identify which categories need updating.
2.  **Fetch Existing Content**: Call `get_article(category_id)` to retrieve the current markdown of the category. You must preserve the human-written context between `<!-- human:start -->` and `<!-- human:end -->`.
3.  **Fetch Children**: Call `get_category_members(category_id)` to get the most up-to-date list of child articles that belong to this category.
4.  **Rewrite AI Block**: Rewrite the markdown exclusively between `<!-- ai:start -->` and `<!-- ai:end -->`. Synthesize a new overview of the topic and list the subcategories and leaf articles with brief descriptions for each, ensuring all new/updated children are represented.
5.  **Save**: Call `save_article()` with your fully updated markdown string for the category.

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

## Related Guides

*   **[[ai-source-code-annotations|AI Source Code Annotations Guide]]**: If you are writing or modifying source code in a project tracked by WikiKnowledge, read this guide to learn how to add the necessary `wk-` metadata to your docstrings so the code natively acts as a virtual article in the graph.
*   **[[ai-settings-and-mcp-binding|AI Settings and MCP Binding]]**: Read this if you want to understand how WikiKnowledge's internal web-based AI assistant is wired to the same MCP tools you are using.