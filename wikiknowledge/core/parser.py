"""
Wiki-link parser
:wk-id: wk/link-parser
:wk-tags: python, parser, regex, markdown
:wk-categories: system-architecture

Wiki-link and content block parser. Extracts [[...]] links and human/AI markers.
Links to: [[wiki-link-syntax]], [[human-protected-blocks]], [[src:wikiknowledge/wk/index-engine]]
"""

from __future__ import annotations

import re
from typing import Optional

from wikiknowledge.storage.models import WikiLink, ContentBlock

# Matches [[target]] or [[target|display text]]
# Does NOT match [[file:...]] links (those are handled separately)
WIKI_LINK_RE = re.compile(r"\[\[(?!file:)([^\[\]|]+?)(?:\|([^\[\]]+?))?\]\]", re.IGNORECASE)

# Matches [[file:resource-id]] or [[file:resource-id|display text]]
FILE_LINK_RE = re.compile(r"\[\[file:([^\[\]|]+?)(?:\|([^\[\]]+?))?\]\]", re.IGNORECASE)

# Fenced code block boundaries
CODE_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")

# Human/AI content block markers
HUMAN_START_RE = re.compile(r"^\s*<!--\s*human:start\s*-->\s*$", re.IGNORECASE)
HUMAN_END_RE = re.compile(r"^\s*<!--\s*human:end\s*-->\s*$", re.IGNORECASE)
AI_START_RE = re.compile(r"^\s*<!--\s*ai:start\s*-->\s*$", re.IGNORECASE)
AI_END_RE = re.compile(r"^\s*<!--\s*ai:end\s*-->\s*$", re.IGNORECASE)


def extract_wiki_links(
    source_id: str, content: str
) -> list[WikiLink]:
    """Extract all wiki links from markdown content.

    Extracts both regular [[target]] links and [[file:resource-id]] links.
    Skips links inside fenced code blocks.

    Args:
        source_id: The article ID that contains the links.
        content: The markdown body text (without frontmatter).

    Returns:
        List of WikiLink objects with source, target, display text, and line number.
    """
    links: list[WikiLink] = []
    in_code_block = False
    code_fence_char: Optional[str] = None

    for line_num, line in enumerate(content.splitlines(), start=1):
        # Track fenced code blocks
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

        # Extract regular wiki links from this line
        for match in WIKI_LINK_RE.finditer(line):
            target_id = match.group(1).strip()
            display_text = match.group(2)
            if display_text:
                display_text = display_text.strip()

            links.append(
                WikiLink(
                    source_id=source_id,
                    target_id=target_id,
                    display_text=display_text,
                    line_number=line_num,
                    is_file_link=False,
                )
            )

        # Extract [[file:...]] links from this line
        for match in FILE_LINK_RE.finditer(line):
            target_id = match.group(1).strip()
            display_text = match.group(2)
            if display_text:
                display_text = display_text.strip()

            links.append(
                WikiLink(
                    source_id=source_id,
                    target_id=target_id,
                    display_text=display_text,
                    line_number=line_num,
                    is_file_link=True,
                )
            )

    return links


def parse_content_blocks(content: str) -> list[ContentBlock]:
    """Parse content into human-written, AI-generated, and unmarked blocks.

    Rules:
    - Between <!-- human:start --> and <!-- human:end --> → "human"
    - Between <!-- ai:start --> and <!-- ai:end --> → "ai"
    - Everything else → "unmarked" (treated as human-written, safe by default)

    Args:
        content: The markdown body text.

    Returns:
        List of ContentBlock objects in order.

    Raises:
        ValueError: If markers are nested or mismatched.
    """
    blocks: list[ContentBlock] = []
    lines = content.splitlines(keepends=True)

    current_type = "unmarked"
    current_lines: list[str] = []
    current_start = 1

    for line_num, line in enumerate(lines, start=1):
        stripped = line

        if current_type == "unmarked":
            if HUMAN_START_RE.match(stripped):
                # Flush unmarked block
                if current_lines:
                    blocks.append(ContentBlock(
                        content="".join(current_lines),
                        block_type="unmarked",
                        start_line=current_start,
                        end_line=line_num - 1,
                    ))
                current_type = "human"
                current_lines = [line]
                current_start = line_num
            elif AI_START_RE.match(stripped):
                if current_lines:
                    blocks.append(ContentBlock(
                        content="".join(current_lines),
                        block_type="unmarked",
                        start_line=current_start,
                        end_line=line_num - 1,
                    ))
                current_type = "ai"
                current_lines = [line]
                current_start = line_num
            else:
                current_lines.append(line)

        elif current_type == "human":
            current_lines.append(line)
            if HUMAN_START_RE.match(stripped):
                raise ValueError(
                    f"Nested <!-- human:start --> at line {line_num}"
                )
            if HUMAN_END_RE.match(stripped):
                blocks.append(ContentBlock(
                    content="".join(current_lines),
                    block_type="human",
                    start_line=current_start,
                    end_line=line_num,
                ))
                current_type = "unmarked"
                current_lines = []
                current_start = line_num + 1

        elif current_type == "ai":
            current_lines.append(line)
            if AI_START_RE.match(stripped):
                raise ValueError(
                    f"Nested <!-- ai:start --> at line {line_num}"
                )
            if AI_END_RE.match(stripped):
                blocks.append(ContentBlock(
                    content="".join(current_lines),
                    block_type="ai",
                    start_line=current_start,
                    end_line=line_num,
                ))
                current_type = "unmarked"
                current_lines = []
                current_start = line_num + 1

    # Flush remaining content
    if current_lines:
        if current_type != "unmarked":
            raise ValueError(
                f"Unclosed <!-- {current_type}:start --> block starting at line {current_start}"
            )
        blocks.append(ContentBlock(
            content="".join(current_lines),
            block_type="unmarked",
            start_line=current_start,
            end_line=len(lines),
        ))

    return blocks
