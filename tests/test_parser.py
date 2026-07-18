import pytest
from wikiknowledge.core.parser import extract_wiki_links, parse_content_blocks
from wikiknowledge.storage.models import WikiLink, ContentBlock

def test_extract_wiki_links_basic():
    content = "Here is a [[basic-link]] and a [[link-with-text|Display Text]]."
    links = extract_wiki_links("source-1", content)
    assert len(links) == 2
    
    assert links[0].source_id == "source-1"
    assert links[0].target_id == "basic-link"
    assert links[0].display_text is None
    assert links[0].line_number == 1
    assert links[0].is_file_link is False
    
    assert links[1].source_id == "source-1"
    assert links[1].target_id == "link-with-text"
    assert links[1].display_text == "Display Text"
    assert links[1].line_number == 1
    assert links[1].is_file_link is False

def test_extract_wiki_links_file():
    content = "See [[file:image.png]] or [[file:doc.pdf|Read Document]]."
    links = extract_wiki_links("source-1", content)
    assert len(links) == 2
    
    assert links[0].target_id == "image.png"
    assert links[0].is_file_link is True
    assert links[0].display_text is None
    
    assert links[1].target_id == "doc.pdf"
    assert links[1].is_file_link is True
    assert links[1].display_text == "Read Document"

def test_extract_wiki_links_code_blocks():
    content = """Some text with [[link1]].
```python
# A comment with [[link2]]
```
More text with [[link3]]."""
    links = extract_wiki_links("source-1", content)
    assert len(links) == 2
    assert links[0].target_id == "link1"
    assert links[0].line_number == 1
    assert links[1].target_id == "link3"
    assert links[1].line_number == 5

def test_extract_wiki_links_multiline():
    content = "Line 1: [[link1]]\nLine 2: [[link2]]"
    links = extract_wiki_links("source-1", content)
    assert len(links) == 2
    assert links[0].line_number == 1
    assert links[1].line_number == 2

def test_parse_content_blocks_unmarked():
    content = "Just some\nnormal text."
    blocks = parse_content_blocks(content)
    assert len(blocks) == 1
    assert blocks[0].block_type == "unmarked"
    assert blocks[0].content == "Just some\nnormal text."
    assert blocks[0].start_line == 1
    assert blocks[0].end_line == 2

def test_parse_content_blocks_human_ai():
    content = """Start unmarked
<!-- human:start -->
Human text
<!-- human:end -->
<!-- ai:start -->
AI text
<!-- ai:end -->
End unmarked"""
    blocks = parse_content_blocks(content)
    assert len(blocks) == 4
    
    assert blocks[0].block_type == "unmarked"
    assert blocks[0].content == "Start unmarked\n"
    
    assert blocks[1].block_type == "human"
    assert blocks[1].content == "<!-- human:start -->\nHuman text\n<!-- human:end -->\n"
    
    assert blocks[2].block_type == "ai"
    assert blocks[2].content == "<!-- ai:start -->\nAI text\n<!-- ai:end -->\n"
    
    assert blocks[3].block_type == "unmarked"
    assert blocks[3].content == "End unmarked"

def test_parse_content_blocks_nested_error():
    content = """<!-- human:start -->
<!-- human:start -->
Oops
<!-- human:end -->
<!-- human:end -->"""
    with pytest.raises(ValueError, match="Nested <!-- human:start --> at line 2"):
        parse_content_blocks(content)

def test_parse_content_blocks_unclosed_error():
    content = "<!-- ai:start -->\nText but no end"
    with pytest.raises(ValueError, match="Unclosed <!-- ai:start --> block starting at line 1"):
        parse_content_blocks(content)
