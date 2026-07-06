# Open Questions

Design decisions that need user input before proceeding. These are recorded here for persistence across sessions.

---

## 1. Metadata Field Prefix

**Question**: What prefix should the metadata fields use in source annotations?

**Current proposal**: `wk-` (short for WikiKnowledge)
- Python: `:wk-id:`, `:wk-tags:`, `:wk-categories:`
- JavaScript: `@wk-id`, `@wk-tags`, `@wk-categories`

**Alternatives considered**:
- `wiki-` — more descriptive but longer
- `kb-` — "knowledge base" — generic
- `wikiknowledge-` — fully qualified but very verbose

**Status**: Proposed `wk-` — awaiting confirmation.

---

## 2. Source Link Prefix

**Question**: What prefix to use for source-qualified wiki links?

**Current proposal**: `src:` → `[[src:wk/index-engine]]`

**Alternatives considered**:
- `code:` — explicit about source code, but doesn't generalize to non-code plugins
- `ext:` — generic "external", but too vague
- `source:` — fully spelled out, but verbose in links

**Status**: Proposed `src:` — awaiting confirmation.

---

## 3. Article ID Format for Virtual Articles

**Question**: How should virtual article IDs be structured?

**Current proposal**: `src:source-name/module-path`
- The `src:` prefix is part of the ID, making it globally unique
- Example: `src:wk/index-engine`, `src:myapp/auth-service`

**Alternative**: Keep the `src:` only in link syntax, and use `source-name/module-path` as the bare ID in the index
- Pro: Simpler IDs in the index
- Con: Potential collision with wiki article IDs that contain `/`

**Status**: Proposed `src:` as part of ID — awaiting confirmation.

---

## 4. Configuration File Location — RESOLVED

**Decision**: Split configuration into two files with distinct roles.

### Declaration file: `knowledge/sources.json`
- **Purpose**: Declares what sources exist, how to parse them, and their default location (relative path).
- **Versioned**: Yes — committed to the repo, travels with the knowledge base.
- **Content**: Source definitions including type, description, language settings, include/exclude patterns, default relative path (for same-repo sources), and connected KB names.

### Settings override: `knowledge/.settings/sources.json`
- **Purpose**: Machine-specific path overrides for sources whose actual location differs from the declaration's default relative path.
- **Versioned**: No (`.settings/` is typically gitignored) — each developer/machine can have different paths.
- **Content**: Simple source-name → actual-path mapping.

### Rationale
- The declaration describes the *structure* of the connection (what to scan, how to parse) — this is part of the KB's identity.
- The settings describe the *location* on this specific machine — this varies per developer/deployment.
- For same-repo sources (e.g., WikiKnowledge annotating itself), the default relative path in the declaration file is sufficient — no settings override needed.

**Status**: ✅ Resolved per user direction.

---

## 5. Should Source Annotations Be Parsed for the Dogfood Phase?

**Question**: In Phase 1, we're only writing documentation + annotations. Should we also write a minimal parser that can at least validate the annotations (even without the full plugin runtime)?

**Current thinking**: No — keep Phase 1 purely documentation. The annotations are useful as regular code documentation regardless. Phase 2 builds the parser.

**Status**: Proceeding with documentation-only approach unless directed otherwise.
