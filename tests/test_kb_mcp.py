"""End-to-end tests for the kb-mcp stdio shim."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from wikiknowledge.tools import kbctl

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def scratch_config(tmp_path: Path, port: int) -> Path:
    kb_dir = tmp_path / "kb"
    (kb_dir / "articles").mkdir(parents=True)
    (kb_dir / "categories").mkdir()
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps({"knowledge_bases": {"Scratch": {"kb_dir": str(kb_dir), "port": port}}})
    )
    return config


def start_shim(config: Path, state_dir: Path, idle: float) -> subprocess.Popen:
    return subprocess.Popen(
        [
            sys.executable, "-m", "wikiknowledge.tools.kb_mcp",
            "--config", str(config), "--state-dir", str(state_dir),
            "--idle", str(idle), "Scratch",
        ],
        cwd=PROJECT_ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )


def send(shim: subprocess.Popen, message: dict) -> None:
    shim.stdin.write(json.dumps(message) + "\n")
    shim.stdin.flush()


def receive(shim: subprocess.Popen, timeout: float = 120.0) -> dict:
    """Read one JSON-RPC message. Anything non-JSON on stdout is a protocol bug."""
    box: dict = {}

    def reader():
        box["line"] = shim.stdout.readline()

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    thread.join(timeout)
    if "line" not in box:
        raise TimeoutError("shim produced no message")
    return json.loads(box["line"])


def handshake(shim: subprocess.Popen) -> dict:
    send(shim, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "kb-mcp-test", "version": "0"},
        },
    })
    response = receive(shim)
    send(shim, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    return response


@pytest.mark.slow
def test_shim_starts_a_stopped_instance_and_relays_a_real_mcp_session(tmp_path):
    port = free_port()
    config = scratch_config(tmp_path, port)
    runtime = kbctl.Runtime(state_dir=tmp_path / "run")
    assert kbctl.is_listening(port) is False

    shim = start_shim(config, tmp_path / "run", idle=600)
    try:
        assert handshake(shim)["result"]["serverInfo"]["name"]

        send(shim, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        listed = receive(shim)

        assert listed["id"] == 2
        assert listed["result"]["tools"], "no tools came back through the relay"
    finally:
        shim.kill()
        shim.wait()
        kbctl.stop("Scratch", runtime)


@pytest.mark.slow
def test_instance_is_released_and_reaped_after_the_client_disconnects(tmp_path):
    port = free_port()
    config = scratch_config(tmp_path, port)
    runtime = kbctl.Runtime(state_dir=tmp_path / "run")

    shim = start_shim(config, tmp_path / "run", idle=0.5)
    try:
        handshake(shim)
        assert runtime.lease_holders("Scratch") == [shim.pid]

        shim.stdin.close()
        shim.wait(timeout=30)

        # Forgetting the instance is the reaper's last step, so wait for that
        # rather than for the port, which frees a moment earlier.
        deadline = time.monotonic() + 30
        while runtime.state("Scratch") is not None and time.monotonic() < deadline:
            time.sleep(0.3)

        assert runtime.state("Scratch") is None, "idle instance was never reaped"
        assert kbctl.is_listening(port) is False
    finally:
        if shim.poll() is None:
            shim.kill()
            shim.wait()
        kbctl.stop("Scratch", runtime)
