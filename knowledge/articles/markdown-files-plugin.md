---
categories:
- knowledge-sources
created: '2026-08-17T00:00:00.000000+00:00'
id: markdown-files-plugin
modified: '2026-08-17T00:00:00.000000+00:00'
tags:
- knowledge-sources
- markdown
- plugin
- hierarchy
- documentation
title: Markdown Files Plugin
type: leaf
---

# Markdown Files Plugin

The Markdown Files Plugin imports an existing folder tree of plain markdown documentation (Docusaurus, MkDocs, Docsify, or just a `docs/` directory in a repository) into the knowledge graph as virtual articles.

Unlike the [[source-code-plugin|Source Code Plugin]], the source files need no WikiKnowledge annotations at all — the plugin derives structure from the filesystem hierarchy and, when present, from YAML frontmatter.

## Folders Become Categories

WikiKnowledge has a flat ID space with an explicit category graph, while markdown documentation portals are hierarchical. The plugin bridges the two:

- Every folder containing indexed markdown becomes a **category article**.
- Every markdown file becomes a **leaf article**, categorized under its containing folder.
- Nested folders are categorized under their parent folder.
- Top-level items are attached to the KB categories listed in the source's `categories` config field (empty by default).
- Category articles get a generated `## Contents` section linking to their members.

### Index Files

A file named `index`, `readme`, `_index`, or `_category_` **represents its folder** rather than being a separate article: its content and frontmatter become the folder's category article. The same happens for a file sitting next to a folder of the same name (`guides.md` alongside `guides/`), a common Docusaurus layout.

## Article IDs

Article IDs are the dash-concatenated, slugified relative path with the extension stripped, namespaced by the source with the same `src:` prefix as the [[source-link-syntax|Source Link Syntax]] uses:

| File | Article ID |
|------|-----------|
| `intro.md` | `src:docs/intro` |
| `tutorial/auth/login.md` | `src:docs/tutorial-auth-login` |
| `tutorial/index.md` | `src:docs/tutorial` |

Using the full path rather than just the filename guarantees uniqueness across the tree. If two different files still collide after slugification, a numeric suffix is appended and a warning is printed.

## Link Conversion

Plain markdown uses relative file links, which are meaningless in a flat wiki. Links are rewritten when the article is served:

| Source link | Result |
|-------------|--------|
| `[Login](../auth/login.md)` | `[[src:docs/auth-login\|Login]]` |
| `[Login](../auth/login)` (extension-less slug) | `[[src:docs/auth-login\|Login]]` |
| `[Guides](./guides)` (folder) | `[[src:docs/guides\|Guides]]` |
| `[Anchor](./login.md#setup)` | `[[src:docs/login\|Anchor]]` (anchor dropped) |
| `![Diagram](./flow.png)` | `![Diagram](/api/sources/docs/assets/flow.png)` |
| `[Site](https://example.com)` | unchanged |

Content inside fenced code blocks is never rewritten, and links that cannot be resolved inside the source root are left untouched.

### Asset Serving

Images and other non-markdown files referenced by imported articles are served by `GET /api/sources/{source_id}/assets/{path}`, which reads from the source root with path-traversal protection. This makes diagrams and screenshots render normally in the viewer without copying them into the knowledge base.

## Frontmatter

Frontmatter is optional — documentation sets without it work fine — but is used when present:

- `title` (or `sidebar_label`) → article title. Falls back to the first `# H1`, then to the humanized filename.
- `tags` (or `keywords`) → article tags, list or comma-separated string.
- `categories` (or `wk-categories`) → additional categories, on top of the folder hierarchy.

## Configuration

Declared in `knowledge/sources.json` with `"type": "markdown-files"`. The path resolves from `default_path` or is overridden per machine in `.settings/sources.json`, exactly like the [[source-code-plugin|Source Code Plugin]]:

```json
{
  "sources": {
    "docs": {
      "type": "markdown-files",
      "description": "Public documentation portal",
      "default_path": "../external-docs/docs",
      "knowledge_bases": { "default": "self" },
      "include": ["./**/*.md", "./**/*.mdx"],
      "exclude": ["./**/node_modules/**", "./**/.docusaurus/**"],
      "tags": ["documentation"]
    }
  }
}
```

| Field | Default | Purpose |
|-------|---------|---------|
| `include` | `["**/*.md"]` | Whitelist glob patterns, relative to the source root |
| `exclude` | `[]` | Blacklist glob patterns, applied after `include` |
| `folders_as_categories` | `true` | Set to `false` for a flat import |
| `categories` | `[]` | KB categories the top level of the tree is attached to |
| `tags` | `[]` | Tags added to every imported article |
| `root_id` | source name | ID stem used when the root itself needs an article |

Only `.md`, `.mdx`, and `.markdown` files are indexed, regardless of the include patterns.

## Behaviour

Imported articles are read-only from the wiki side, like all virtual articles — edits belong in the source repository. `POST /api/sources/rescan` picks up changes to the documentation tree.
