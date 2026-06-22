---
categories:
- markup-conventions
created: '2026-06-22T05:53:27.653623+00:00'
id: category-features
modified: '2026-06-22T05:53:27.653648+00:00'
tags:
- category
- features
- ui
- index
title: Category Features
type: leaf
---

# Category Features

Category articles in WikiKnowledge are designed to organize and structure knowledge. To improve the user experience and maintain data consistency, category articles have several specialized features that distinguish them from regular leaf articles:

## Sub-articles Section
When viewing a category article, the web UI automatically appends a "Sub-articles" section. This lists all articles (both leaf and nested categories) that belong to the category. It helps readers navigate the category hierarchy even if the category article's content doesn't explicitly mention every member.

## Unmentioned Highlighting
WikiKnowledge encourages authors (and AI summarizers) to explicitly reference sub-articles within the text of a category article. If a sub-article is **not** explicitly linked (e.g. via `[[article-id]]`) anywhere within the category article's content, it receives a special visual highlight in the Sub-articles section. This acts as a hint that the category's narrative might be incomplete or missing newly added knowledge.

## Dirty Indicator
A category article's purpose is to summarize its members. If any sub-article is modified *after* the category article was last modified, the category is considered "dirty" or outdated. A visual warning indicator (⚠️) is displayed next to the Sub-articles section, signaling to the reader (and maintainers) that the summary might not reflect the latest changes in the sub-articles.

## Backlinks Filtering
To reduce noise, the "What links here" (backlinks) section for a category article is filtered. Specifically, it excludes any backlinks coming from its own sub-articles. Since sub-articles intrinsically "link" to their parent category by declaring membership, hiding these implicit backlinks focuses the reader's attention on external references pointing to the category.