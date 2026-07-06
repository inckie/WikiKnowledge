# Extended Wiki-Link Syntax for Knowledge Sources

## Current Syntax (Unchanged)

| Syntax | Purpose | Example |
|--------|---------|---------|
| `[[article-id]]` | Link to a wiki article | `[[storage-abstraction]]` |
| `[[article-id\|Display Text]]` | Link with custom display text | `[[storage-abstraction\|the storage layer]]` |
| `[[file:resource-id]]` | Link to a media resource | `[[file:logo.svg]]` |
| `[[file:resource-id\|Display Text]]` | Resource link with display text | `[[file:logo.svg\|WikiKnowledge Logo]]` |

## New: Source-Qualified Links

### Syntax

```
[[src:source-name/module-path]]
[[src:source-name/module-path|Display Text]]
```

### Components

- `src:` — The link type prefix (like `file:` for resources). Case-insensitive.
- `source-name` — Matches a source declared in the sources configuration. E.g., `wk`.
- `/` — Separator between source name and module path.
- `module-path` — The `wk-id` suffix declared in the source file annotation. E.g., `index-engine`.
- `|Display Text` — Optional custom display text (same as existing syntax).

### Examples

```markdown
The index is built by [[src:wk/index-engine]].
The [[src:wk/markdown-storage|file-system backend]] handles persistence.
See [[src:myapp/auth-service|the authentication module]] for details.
```

### Resolution

1. Parse the `src:` prefix to identify this as a source link
2. Split on the first `/` to get `source-name` and `module-path`
3. Look up the source in the configuration
4. If the source is connected, resolve to the virtual article with ID `src:source-name/module-path`
5. If the source is disconnected, render with a "disconnected source" indicator

### Rendering States

| State | Visual Treatment |
|-------|-----------------|
| **Resolved** | Normal link style, with a small source icon (e.g., `</>`or a code icon) |
| **Disconnected source** | Muted/gray text with a disconnected icon (⊘). Tooltip: "Source 'name' is not connected" |
| **Unknown source** | Red "missing" style (same as unknown wiki articles). The source name doesn't exist in config |
| **Unknown module** | Source is connected but module path doesn't match any annotated file. Red "missing" style |

---

## New: KB-Qualified Links (Multi-KB Support)

### Problem

A single source codebase can be connected to **multiple WikiKnowledge knowledge bases**. When a source annotation contains `[[storage-abstraction]]`, which KB's article does it refer to?

### Design Principle

If there is only one connected KB (the common case), **no additional syntax is needed** — all unqualified wiki links resolve against that default KB. The `@kb-name` qualifier is only needed when a source links to articles in a non-default KB.

### Syntax

```
[[article-id@kb-name]]
[[article-id@kb-name|Display Text]]
[[src:source-name/module-path@kb-name]]
```

The `@kb-name` suffix is appended before the optional `|Display Text`, and works with all link types.

### Components

- `@kb-name` — Optional KB qualifier. `kb-name` matches a knowledge base name declared in the source's connection configuration.
- If omitted, the link resolves against the **default KB** (the KB that loaded this source, or the first one declared).

### Examples

```markdown
# In source code annotations when connected to multiple KBs:

The auth flow is documented in [[api-authentication@api-docs]].
For the overall design, see [[security-architecture]].
The implementation follows [[src:myapp/auth-handler@main-wiki]].
```

```markdown
# In wiki articles — rarely needed, but supported:

The external API spec is described in [[rest-endpoints@partner-wiki]].
```

### Resolution

1. Parse the `@kb-name` suffix (if present) from the link target
2. If `kb-name` is provided, look up that KB in the source's connection configuration
3. If `kb-name` is absent, resolve against the default KB
4. Resolve the article/source ID within the target KB

### Rendering States

| State | Visual Treatment |
|-------|-----------------|
| **Resolved (default KB)** | Normal link — no KB indicator needed |
| **Resolved (named KB)** | Normal link with a small KB badge showing the KB name |
| **Unknown KB name** | Red "missing" style. The `@kb-name` doesn't match any configured KB |
| **KB disconnected** | Muted/gray with disconnected icon (⊘). The KB exists in config but is unreachable |

### Interaction with Source Links

The `@kb-name` qualifier can combine with `src:` links:

| Syntax | Meaning |
|--------|---------|
| `[[src:wk/index-engine]]` | Source article from source "wk" — resolved in the current/default KB |
| `[[src:wk/index-engine@docs-wiki]]` | Source article from source "wk" as seen by the "docs-wiki" KB |
| `[[storage-abstraction@main-wiki]]` | Wiki article in a specific KB |
| `[[storage-abstraction]]` | Wiki article in the default KB (unchanged behavior) |

### Configuration of KB Names

KB names are declared in the source's declaration file (`knowledge/sources.json`):

```json
{
  "sources": {
    "myapp": {
      "type": "source-code",
      "default_path": "../myapp",
      "knowledge_bases": {
        "default": "self",
        "api-docs": { "url": "http://localhost:8002" }
      },
      "languages": { ... }
    }
  }
}
```

- `"default": "self"` — the KB that owns this declaration file; no `@` needed in links
- Other entries map a `kb-name` to a connection reference (URL, path, etc.)

For the common single-KB case, the `knowledge_bases` key can be omitted entirely — all links resolve against the current KB.

---

## Bidirectional Linking

Source links participate fully in the link graph:

- A wiki article containing `[[src:wk/index-engine]]` creates a forward link from that article to the virtual article
- The virtual article's "what links here" (backlinks) will show the wiki article
- Wiki links inside source-code annotations (e.g., `[[storage-abstraction]]` in a Python docstring) create forward links from the virtual article to the wiki article
- Cross-source links (`[[src:other-project/module]]` in a source annotation) create links between virtual articles from different sources
- KB-qualified links (`[[article@other-kb]]`) create cross-KB link records; the target KB may track these as external backlinks

---

## Parser Changes Required

The existing `WIKI_LINK_RE` and `FILE_LINK_RE` in `wikiknowledge/core/parser.py` would need new companions:

```python
# Matches [[src:source-name/module-path]] or with display text and optional @kb
SOURCE_LINK_RE = re.compile(
    r"\[\[src:([^/\[\]|@]+)/([^\[\]|@]+?)(?:@([^\[\]|]+?))?(?:\|([^\[\]]+?))?\]\]",
    re.IGNORECASE
)
# Groups: 1=source-name, 2=module-path, 3=kb-name (optional), 4=display-text (optional)

# Matches [[article-id@kb-name]] (KB-qualified wiki link)
# Must not match src: or file: links (handled separately)
KB_QUALIFIED_LINK_RE = re.compile(
    r"\[\[(?!src:|file:)([^\[\]|@]+?)@([^\[\]|]+?)(?:\|([^\[\]]+?))?\]\]",
    re.IGNORECASE
)
# Groups: 1=article-id, 2=kb-name, 3=display-text (optional)
```

The `extract_wiki_links()` function would produce `WikiLink` objects with appropriate target IDs. KB-qualified links would encode the KB name in the target ID (e.g., `article-id@kb-name`) or in a new field on `WikiLink`.

## Alternative Prefix Considered

| Prefix | Pros | Cons |
|--------|------|------|
| `src:` | Short, clear, familiar from version control | Could be confused with "source" in HTML sense |
| `code:` | Very explicit about source code | Doesn't generalize to non-code plugins |
| `ext:` | Generic "external" — works for all plugin types | Too vague, doesn't convey what it links to |
| `source:` | Fully spelled out | Verbose, long in links |

**Decision**: Use `src:` for the source-code plugin. If future plugins need their own prefixes, they can have them (e.g., `remote:` for remote wikis). The parser should be designed to handle arbitrary `prefix:` patterns.

## Interaction with Existing Link Features

- **Backlinks**: `get_backlinks()` on a virtual article returns all wiki/source articles linking to it
- **Graph visualization**: Source links become edges in the D3 graph. Virtual article nodes have a distinct visual type
- **Search**: Source link targets are included in search results
- **Category membership**: If a source-code annotation declares `wk-categories: system-architecture`, the virtual article appears as a member of that category
- **Broken link detection**: Source links to disconnected sources are tracked separately from truly broken links
- **KB-qualified links**: Cross-KB links are tracked; when the target KB is unreachable, they degrade to "disconnected" (not "broken")
