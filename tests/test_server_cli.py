"""Tests for the WikiKnowledge server command line."""

from __future__ import annotations

from wikiknowledge.api import app


def test_server_reloads_by_default_so_interactive_development_is_unchanged():
    assert app.parse_server_args([]).reload is True


def test_reload_can_be_switched_off_for_background_instances():
    assert app.parse_server_args(["--no-reload"]).reload is False


def test_port_and_kb_dir_are_still_parsed():
    args = app.parse_server_args(["--port=8004", "--kb-dir=/tmp/kb"])

    assert (args.port, args.kb_dir) == (8004, "/tmp/kb")
