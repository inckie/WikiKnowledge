---
categories:
- system-architecture
created: '2026-06-19T21:00:00+00:00'
id: markup-conventions
modified: '2026-07-17T05:24:33.684175+00:00'
tags:
- markup
- conventions
- syntax
- documentation
title: Markup Conventions
type: category
---

<!-- human:start -->
WikiKnowledge extends standard Markdown with a small set of conventions that enable structured knowledge management. These conventions are deliberately minimal — a plain Markdown file with no extensions is still a valid article (it just won't have metadata or internal links).

The conventions fall into three categories:

1. **Metadata** — YAML frontmatter at the top of every file provides structured fields (title, tags, categories, timestamps) that the system indexes and the UI renders as interactive controls.

2. **Linking** — Double-bracket wiki links (`[[target-id]]` or `[[target-id|Display Text]]`) create connections between articles. These links are the raw material from which the knowledge graph is built.

3. **Authorship** — HTML comment markers (`<!-- human:start -->` / `<!-- human:end -->` and `<!-- ai:start -->` / `<!-- ai:end -->`) delineate human-written and AI-generated sections in category articles. This ensures that AI summarization preserves the human architect's vision while automatically updating the content summaries.

All three conventions are designed to degrade gracefully: a file with missing frontmatter is treated as having default metadata; unresolved wiki links are displayed with a "missing" indicator; and content without authorship markers is assumed to be human-written.
<!-- human:end -->

## Articles in This Category

<!-- ai:start -->
### [[markdown-frontmatter|Markdown Frontmatter Convention]]
Documents the YAML frontmatter format used at the top of every `.md` file. Covers required fields (`id`, `title`, `type`, `tags`, `categories`, `created`, `modified`), parsing with the `python-frontmatter` library, and the design rationale for choosing YAML frontmatter over alternatives like sidecar files or database records.

### [[wiki-link-syntax|Wiki Link Syntax]]
Explains the `[[article-id]]` and `[[article-id|Display Text]]` double-bracket syntax for internal links. Covers resolution rules (case-sensitive matching against the `id` field), extraction and indexing (forward links + back links), edge cases (self-links, links in code blocks), and the relationship between wiki links and the knowledge graph.

### [[source-link-syntax|Source Link Syntax]]
Documents the extended wiki-link syntax used to reference virtual articles from external knowledge sources. Covers source-qualified link prefixes (`src:` and `gdrive:`), link resolution rules, multi-KB `@kb-name` qualifiers, and how disconnected sources degrade gracefully in the UI.

### [[human-protected-blocks|Human-Protected Blocks]]
Describes the HTML comment marker system for distinguishing human-written content from AI-generated summaries in category articles. Covers the `<!-- human:start/end -->` and `<!-- ai:start/end -->` syntax, the "safe by default" rule (unmarked content is treated as human), nesting restrictions, and the visual indicators shown in the web UI.

### [[category-features|Category Features]]
Details the specialized UI and data consistency features for category articles. This includes the automatic "Sub-articles" section, highlighting of unmentioned sub-articles to prompt authors for updates, a "dirty" indicator (⚠️) when a category's summary may be out of sync with its members, and intelligent backlink filtering to reduce noise from sub-article references.

### [[mermaid-diagrams|Mermaid Diagrams]]
Documentation of Mermaid support. To embed a diagram, use a standard markdown fenced code block and specify mermaid as the language.
<!-- ai:end -->