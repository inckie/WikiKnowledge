"""Transclusion Engine

:wk-id: transclusion-engine
:wk-tags: python, transclusion, engine, mcp, syntax
:wk-categories: system-architecture

Transclusion resolution and section extraction engine.

Supports transcluding full articles or individual sections from:
- Native wiki pages
- Markdown file plugin (src:...)
- Source code plugin docblocks (src:...)
- Google Drive documents (gdrive:...)

Handles disconnected sources, missing articles/sections, and circular transclusions gracefully.
Formats output for both the Web UI (HTML boxed component) and AI agents via MCP (annotated markdown blockquote).
"""

from __future__ import annotations

import re
from typing import Optional, Any

# Matches ![[target]] or ![[target#section]] or ![[target|display text]]
TRANSCLUSION_LINK_RE = re.compile(r"!\[\[([^\[\]|]+?)(?:\|([^\[\]]+?))?\]\]", re.IGNORECASE)

# Fenced code block boundaries
CODE_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")

# ATX Markdown heading regex: matches '# Heading', '## Heading ###'
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)(?:\s+#+)?$")

# Frontmatter boundary regex
FRONTMATTER_RE = re.compile(r"^---\s*\n([\s\S]*?)\n---\s*\n")


def slugify(text: str) -> str:
    """Generate a URL-safe heading slug matching frontend Utils.slugify()."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def strip_frontmatter(content: str) -> str:
    """Remove YAML frontmatter if present at the top of content."""
    match = FRONTMATTER_RE.match(content)
    if match:
        return content[match.end():]
    return content


def check_source_disconnected(target_id: str, source_manager: Any) -> tuple[bool, Optional[str]]:
    """Check if the source providing target_id is configured but currently disconnected."""
    if not source_manager:
        return False, None

    if target_id.startswith("src:"):
        parts = target_id[4:].split("/", 1)
        source_name = parts[0] if parts else ""
        if hasattr(source_manager, "plugins") and source_name in source_manager.plugins:
            plugin = source_manager.plugins[source_name]
            if not plugin.is_available():
                return True, source_name
    elif target_id.startswith("gdrive:"):
        if hasattr(source_manager, "get_google_drive_plugin"):
            plugin = source_manager.get_google_drive_plugin(target_id)
            if plugin and not plugin.is_available():
                return True, plugin.source_name
        if hasattr(source_manager, "plugins"):
            for sname, plug in source_manager.plugins.items():
                if "GoogleDrive" in type(plug).__name__ and not plug.is_available():
                    return True, sname
    return False, None


def extract_section(content: str, section_spec: str) -> Optional[tuple[str, str, int]]:
    """Extract a section from markdown content matching a section spec.

    Matches by:
    1. Exact heading title (case-insensitive)
    2. Heading slug (matches slugify(heading_text))
    3. Block ID marker (future support for '^block-id')

    Args:
        content: Markdown content (without frontmatter).
        section_spec: Section name, slug, or block ID (e.g. 'Basic Syntax', 'basic-syntax', '^block-1').

    Returns:
        Tuple of (section_body, matched_heading_title, heading_level), or None if not found.
    """
    clean_spec = section_spec.strip().lstrip("#").strip()
    if not clean_spec:
        return None

    # Future block ID support: '^block-id'
    if clean_spec.startswith("^"):
        block_id = clean_spec[1:]
        block_pattern = re.compile(rf"\^{re.escape(block_id)}\s*$", re.MULTILINE)
        match = block_pattern.search(content)
        if match:
            # Slices the block/paragraph ending at the block marker
            start_pos = content.rfind("\n\n", 0, match.start())
            start_pos = 0 if start_pos == -1 else start_pos + 2
            end_pos = match.end()
            block_content = content[start_pos:end_pos].strip()
            # Clean off the block id marker for display
            display_content = re.sub(rf"\s*\^{re.escape(block_id)}\s*$", "", block_content)
            return (display_content, f"^{block_id}", 0)
        return None

    lines = content.splitlines()
    spec_slug = slugify(clean_spec)
    spec_lower = clean_spec.lower()

    in_code_block = False
    code_fence_char: Optional[str] = None

    matched_index = -1
    matched_title = ""
    matched_level = 0

    for i, line in enumerate(lines):
        fence_match = CODE_FENCE_RE.match(line.strip())
        if fence_match:
            fence = fence_match.group(1)
            if not in_code_block:
                in_code_block = True
                code_fence_char = fence[0]
            elif fence[0] == code_fence_char:
                in_code_block = False
                code_fence_char = None
            continue

        if in_code_block:
            continue

        heading_match = HEADING_RE.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            raw_title = heading_match.group(2).strip()
            # Strip markdown formatting from title (e.g. bold, code, links)
            clean_title = re.sub(r"[*_`]", "", raw_title).strip()
            clean_title = re.sub(r"\[\[([^|\]]+)(?:\|[^\]]+)?\]\]", r"\1", clean_title)

            if clean_title.lower() == spec_lower or slugify(clean_title) == spec_slug:
                matched_index = i
                matched_title = clean_title
                matched_level = level
                break

    if matched_index == -1:
        return None

    # Collect section body lines until next heading with level <= matched_level
    section_lines: list[str] = []
    in_code_block = False
    code_fence_char = None

    for line in lines[matched_index + 1:]:
        fence_match = CODE_FENCE_RE.match(line.strip())
        if fence_match:
            fence = fence_match.group(1)
            if not in_code_block:
                in_code_block = True
                code_fence_char = fence[0]
            elif fence[0] == code_fence_char:
                in_code_block = False
                code_fence_char = None
            section_lines.append(line)
            continue

        if not in_code_block:
            heading_match = HEADING_RE.match(line)
            if heading_match:
                level = len(heading_match.group(1))
                if level <= matched_level:
                    # Reached an equal or higher level section heading; end of section
                    break

        section_lines.append(line)

    section_body = "\n".join(section_lines).strip()
    return (section_body, matched_title, matched_level)


async def resolve_transclusions(
    content: str,
    current_article_id: str,
    storage: Any,
    source_manager: Any,
    index: Any,
    format: str = "html",
    call_chain: Optional[set[str]] = None,
    depth: int = 0,
) -> str:
    """Recursively resolve all ![[...]] transclusions in markdown content.

    Args:
        content: Markdown content to process.
        current_article_id: ID of the article containing the transclusions.
        storage: MarkdownStorageBackend instance.
        source_manager: SourceManager instance (for virtual articles).
        index: KnowledgeIndex instance (for metadata).
        format: 'html' for web UI viewer, or 'markdown' for AI/MCP.
        call_chain: Set of article/section keys currently being resolved (for cycle detection).
        depth: Current recursion depth.

    Returns:
        Content with transclusions replaced by boxed HTML markers or annotated markdown.
    """
    if not content or "![" not in content:
        return content

    chain = set(call_chain or ())
    chain.add(current_article_id)

    # Protect code blocks and inline code from regex substitution
    code_blocks: list[str] = []

    def save_code(m: re.Match) -> str:
        code_blocks.append(m.group(0))
        return f"__WK_TRANSCLUDE_CODE_{len(code_blocks) - 1}__"

    protected_content = re.sub(
        r"(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]+`)",
        save_code,
        content,
    )

    matches = list(TRANSCLUSION_LINK_RE.finditer(protected_content))
    if not matches:
        return content

    # Process replacements from end to start to preserve character offsets
    result = protected_content
    for match in reversed(matches):
        raw_target = match.group(1).strip()
        display_title = match.group(2).strip() if match.group(2) else None

        if "#" in raw_target:
            target_id, _, section_spec = raw_target.partition("#")
            target_id = target_id.strip() or current_article_id
            section_spec = section_spec.strip() or None
        else:
            target_id = raw_target
            section_spec = None

        spec_key = f"{target_id}#{section_spec}" if section_spec else target_id

        # 1. Circular transclusion check
        if spec_key in chain or (not section_spec and target_id == current_article_id):
            cycle_desc = f"{current_article_id} -> {spec_key}"
            if format == "markdown":
                replacement = f"> ⚠️ **Circular transclusion detected: {cycle_desc}**\n"
            else:
                replacement = (
                    f'<!-- transclusion:start error="true" id="{target_id}" '
                    f'label="Circular transclusion: {cycle_desc}" icon="⚠️" -->\n'
                    f'<!-- transclusion:end -->'
                )
            result = result[:match.start()] + replacement + result[match.end():]
            continue

        # 2. Depth limit check
        if depth >= 3:
            if format == "markdown":
                replacement = f"> ⚠️ **Transclusion depth limit reached for [[{target_id}]]**\n"
            else:
                replacement = (
                    f'<!-- transclusion:start error="true" id="{target_id}" '
                    f'label="Transclusion depth limit reached" icon="⚠️" -->\n'
                    f'<!-- transclusion:end -->'
                )
            result = result[:match.start()] + replacement + result[match.end():]
            continue

        # 3. Check for disconnected sources before or during content retrieval
        is_disconnected, disconnected_source_name = check_source_disconnected(target_id, source_manager)
        meta = index.get_meta(target_id) if index else None

        if is_disconnected:
            article_title = meta.title if meta else target_id
            section_title = section_spec
            display_label = display_title or (f"{article_title} > {section_title}" if section_title else article_title)

            if format == "markdown":
                replacement = (
                    f"\n> ⊘ **Transcluded content unavailable (Source disconnected): [[{target_id}{f'#{section_spec}' if section_spec else ''}|{display_label}]]**\n"
                    f">\n"
                    f"> *The source '{disconnected_source_name or target_id}' is currently disconnected.*\n"
                )
            else:
                replacement = (
                    f'\n<!-- transclusion:start disconnected="true" id="{target_id}" '
                    f'label="{display_label}" source="{disconnected_source_name or ""}" '
                    f'icon="⊘" badge="Source Disconnected" -->\n'
                    f'<!-- transclusion:end -->\n'
                )
            result = result[:match.start()] + replacement + result[match.end():]
            continue

        # 4. Fetch target content
        target_content = ""
        error_msg = None

        try:
            if target_id.startswith("src:") or target_id.startswith("gdrive:"):
                if not source_manager:
                    raise KeyError(f"Source manager unavailable for '{target_id}'")
                target_content = await source_manager.get_article_content(target_id)
            else:
                article = await storage.get_article(target_id)
                target_content = article.content
                if not meta:
                    meta = article.meta
        except Exception as e:
            err_str = str(e)
            if "disconnected" in err_str.lower():
                article_title = meta.title if meta else target_id
                section_title = section_spec
                display_label = display_title or (f"{article_title} > {section_title}" if section_title else article_title)

                if format == "markdown":
                    replacement = (
                        f"\n> ⊘ **Transcluded content unavailable (Source disconnected): [[{target_id}{f'#{section_spec}' if section_spec else ''}|{display_label}]]**\n"
                        f">\n"
                        f"> *The source is currently disconnected ({err_str}).*\n"
                    )
                else:
                    replacement = (
                        f'\n<!-- transclusion:start disconnected="true" id="{target_id}" '
                        f'label="{display_label}" source="{disconnected_source_name or ""}" '
                        f'icon="⊘" badge="Source Disconnected" -->\n'
                        f'<!-- transclusion:end -->\n'
                    )
                result = result[:match.start()] + replacement + result[match.end():]
                continue
            else:
                error_msg = f"Article '{target_id}' not found ({e})"

        if error_msg:
            jump_url = f"#/article/{target_id}"
            if format == "markdown":
                replacement = f"> ⚠️ **Transclusion missing**: {error_msg}\n"
            else:
                replacement = (
                    f'<!-- transclusion:start error="true" id="{target_id}" '
                    f'label="{error_msg}" url="{jump_url}" icon="⚠️" -->\n'
                    f'<!-- transclusion:end -->'
                )
            result = result[:match.start()] + replacement + result[match.end():]
            continue

        target_content = strip_frontmatter(target_content)

        # 5. Extract section if specified
        matched_heading_title: Optional[str] = None
        if section_spec:
            extracted = extract_section(target_content, section_spec)
            if extracted is None:
                jump_url = f"#/article/{target_id}"
                error_msg = f"Section '{section_spec}' not found in '{target_id}'"
                if format == "markdown":
                    replacement = f"> ⚠️ **{error_msg}** ([Go to Article]({jump_url}))\n"
                else:
                    replacement = (
                        f'<!-- transclusion:start error="true" id="{target_id}" '
                        f'label="{error_msg}" url="{jump_url}" icon="⚠️" -->\n'
                        f'<!-- transclusion:end -->'
                    )
                result = result[:match.start()] + replacement + result[match.end():]
                continue
            section_body, matched_heading_title, _ = extracted
        else:
            section_body = target_content

        # 6. Recursively resolve nested transclusions
        next_chain = set(chain)
        next_chain.add(spec_key)
        resolved_body = await resolve_transclusions(
            content=section_body,
            current_article_id=target_id,
            storage=storage,
            source_manager=source_manager,
            index=index,
            format=format,
            call_chain=next_chain,
            depth=depth + 1,
        )

        # 7. Format presentation attributes
        article_title = meta.title if meta else target_id
        section_title = matched_heading_title or section_spec

        if display_title:
            display_label = display_title
        elif section_title:
            display_label = f"{article_title} > {section_title}"
        else:
            display_label = article_title

        section_slug = slugify(section_title) if section_title else ""
        if section_slug:
            jump_url = f"#/article/{target_id}#{section_slug}"
        else:
            jump_url = f"#/article/{target_id}"

        # Source badge & icon
        if target_id.startswith("src:"):
            icon = "🔌"
            badge = "Source Code"
        elif target_id.startswith("gdrive:"):
            icon = "☁️"
            badge = "Google Drive"
        else:
            icon = "📄"
            badge = "Wiki"

        if format == "markdown":
            # For AI / MCP: format as an indented markdown blockquote
            target_link = f"[[{target_id}{f'#{section_spec}' if section_spec else ''}|{display_label}]]"
            quoted_body = "\n".join(f"> {line}" for line in resolved_body.splitlines())
            replacement = (
                f"\n> 📦 **Transcluded from {target_link}** ([Go to Source]({jump_url})):\n"
                f">\n"
                f"{quoted_body}\n"
            )
        else:
            # For Web UI: format with transclusion comment markers
            # These are converted to boxed HTML by viewer._processTransclusionBlocks()
            replacement = (
                f'\n<!-- transclusion:start id="{target_id}" section="{section_slug}" '
                f'label="{display_label}" url="{jump_url}" badge="{badge}" icon="{icon}" -->\n'
                f'{resolved_body}\n'
                f'<!-- transclusion:end -->\n'
            )

        result = result[:match.start()] + replacement + result[match.end():]

    # Restore code blocks
    for i, code in enumerate(code_blocks):
        result = result.replace(f"__WK_TRANSCLUDE_CODE_{i}__", code)

    return result
