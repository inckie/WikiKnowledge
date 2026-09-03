"""Tests for the WikiKnowledge server command line."""

from __future__ import annotations

from wikiknowledge import cli


def test_server_reloads_by_default_so_interactive_development_is_unchanged():
    assert cli.parse_args([]).reload is True


def test_reload_can_be_switched_off_for_background_instances():
    assert cli.parse_args(["--no-reload"]).reload is False


def test_port_and_kb_dir_are_still_parsed():
    args = cli.parse_args(["--port=8004", "--kb-dir=/tmp/kb"])

    assert (args.port, args.kb_dir) == (8004, "/tmp/kb")


def test_unknown_arguments_are_still_tolerated():
    """`main.py --port=8001 serve-http` is a documented invocation."""
    assert cli.parse_args(["--port=8001", "serve-http"]).port == 8001


import json
import os
import signal
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_kb_dir_is_honoured_with_reload_disabled(tmp_path):
    """With reload on, uvicorn re-imports the app in a child that inherits the
    environment. With reload off there is no child, so --kb-dir has to survive
    on its own."""
    kb_dir = tmp_path / "kb"
    (kb_dir / "articles").mkdir(parents=True)
    (kb_dir / "categories").mkdir()
    (kb_dir / "articles" / "only-here.md").write_text(
        "---\nid: only-here\ntitle: Only Here\ntype: leaf\ntags: []\ncategories: []\n---\n\nMarker.\n"
    )
    port = _free_port()

    server = subprocess.Popen(
        ["uv", "run", "python", "run.py", f"--port={port}", "--no-reload", f"--kb-dir={kb_dir}"],
        cwd=str(PROJECT_ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 90
        articles = None
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/articles", timeout=1) as r:
                    articles = json.load(r)
                    break
            except Exception:
                time.sleep(0.2)
        assert articles is not None, "server never answered"

        ids = {a["id"] for a in articles}
        assert "only-here" in ids
        assert "ai-interaction-guide" not in ids, "the bundled knowledge base leaked in"
    finally:
        os.killpg(os.getpgid(server.pid), signal.SIGTERM)
        server.wait(timeout=30)
