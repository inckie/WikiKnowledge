"""Tests for the kbctl knowledge-base process manager."""

from __future__ import annotations

import contextlib
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from wikiknowledge.tools import kbctl


def write_config(tmp_path: Path, knowledge_bases: dict) -> Path:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"knowledge_bases": knowledge_bases}))
    return config_path


def test_load_config_resolves_relative_kb_dir_against_config_directory(tmp_path):
    (tmp_path / "sibling").mkdir()
    config_path = write_config(tmp_path, {"Sibling": {"kb_dir": "./sibling", "port": 8004}})

    kbs = kbctl.load_config(config_path)

    assert kbs["Sibling"].kb_dir == tmp_path / "sibling"


def test_load_config_treats_empty_kb_dir_as_the_bundled_knowledge_base(tmp_path):
    config_path = write_config(tmp_path, {"self": {"kb_dir": "", "port": 8001}})

    kbs = kbctl.load_config(config_path)

    assert kbs["self"].kb_dir is None


def test_diagnose_reports_a_knowledge_base_whose_directory_is_gone(tmp_path):
    config_path = write_config(tmp_path, {"Stale": {"kb_dir": "./vanished", "port": 8002}})

    problems = kbctl.diagnose(kbctl.load_config(config_path))

    assert [(p.name, p.kind) for p in problems] == [("Stale", "missing-dir")]


def test_diagnose_reports_two_knowledge_bases_sharing_a_port(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    config_path = write_config(
        tmp_path,
        {"A": {"kb_dir": "./a", "port": 8005}, "B": {"kb_dir": "./b", "port": 8005}},
    )

    problems = kbctl.diagnose(kbctl.load_config(config_path))

    assert [p.kind for p in problems] == ["duplicate-port", "duplicate-port"]


def test_diagnose_is_silent_on_a_healthy_config(tmp_path):
    (tmp_path / "kb").mkdir()
    config_path = write_config(tmp_path, {"Fine": {"kb_dir": "./kb", "port": 8006}})

    assert kbctl.diagnose(kbctl.load_config(config_path)) == []


# A PID far above macOS/Linux pid_max: guaranteed to belong to no live process.
DEAD_PID = 999_999


def test_acquired_lease_is_reported_as_a_holder(tmp_path):
    runtime = kbctl.Runtime(state_dir=tmp_path)

    runtime.acquire_lease("self", pid=os.getpid())

    assert runtime.lease_holders("self") == [os.getpid()]


def test_released_lease_is_no_longer_a_holder(tmp_path):
    runtime = kbctl.Runtime(state_dir=tmp_path)
    runtime.acquire_lease("self", pid=os.getpid())

    runtime.release_lease("self", pid=os.getpid())

    assert runtime.lease_holders("self") == []


def test_lease_left_behind_by_a_crashed_process_is_ignored_and_swept(tmp_path):
    runtime = kbctl.Runtime(state_dir=tmp_path)
    runtime.acquire_lease("self", pid=DEAD_PID)

    holders = runtime.lease_holders("self")

    assert holders == []
    assert list((tmp_path / "self" / "leases").iterdir()) == []


def test_instance_started_by_kbctl_with_no_leases_is_reapable(tmp_path):
    runtime = kbctl.Runtime(state_dir=tmp_path)
    runtime.record_start("self", pid=os.getpid(), port=8001, owner=kbctl.OWNER_KBCTL)

    assert runtime.should_reap("self") is True


def test_instance_still_held_by_a_live_lease_is_not_reapable(tmp_path):
    runtime = kbctl.Runtime(state_dir=tmp_path)
    runtime.record_start("self", pid=os.getpid(), port=8001, owner=kbctl.OWNER_KBCTL)
    runtime.acquire_lease("self", pid=os.getpid())

    assert runtime.should_reap("self") is False


def test_instance_started_outside_kbctl_is_never_reapable(tmp_path):
    runtime = kbctl.Runtime(state_dir=tmp_path)
    runtime.record_start("self", pid=os.getpid(), port=8001, owner=kbctl.OWNER_ADOPTED)

    assert runtime.should_reap("self") is False


def test_pinned_instance_is_never_reapable(tmp_path):
    runtime = kbctl.Runtime(state_dir=tmp_path)
    runtime.record_start("self", pid=os.getpid(), port=8001, owner=kbctl.OWNER_KBCTL, pinned=True)

    assert runtime.should_reap("self") is False


def test_instance_kbctl_knows_nothing_about_is_not_reapable(tmp_path):
    runtime = kbctl.Runtime(state_dir=tmp_path)

    assert runtime.should_reap("never-seen") is False


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@contextlib.contextmanager
def stub_kb_server(status: int = 200):
    """A real HTTP server answering the readiness probe, as a live KB would."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(status)
            self.end_headers()
            self.wfile.write(b"[]")

        def log_message(self, *args):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()


def test_port_with_nothing_on_it_is_not_listening():
    assert kbctl.is_listening(free_port()) is False


def test_port_bound_by_a_server_is_listening():
    with stub_kb_server() as port:
        assert kbctl.is_listening(port) is True


def test_readiness_requires_a_real_http_answer_not_just_an_open_socket():
    with socket.socket() as bound:
        bound.bind(("127.0.0.1", 0))
        bound.listen(1)
        port = bound.getsockname()[1]

        assert kbctl.is_listening(port) is True
        assert kbctl.wait_until_ready(port, timeout=0.5) is False


def test_readiness_succeeds_once_the_api_answers():
    with stub_kb_server() as port:
        assert kbctl.wait_until_ready(port, timeout=2.0) is True


def test_ensure_adopts_an_instance_that_is_already_serving(tmp_path):
    runtime = kbctl.Runtime(state_dir=tmp_path)
    with stub_kb_server() as port:
        kb = kbctl.KnowledgeBase(name="Applicaster", port=port, kb_dir=None)

        url = kbctl.ensure(kb, runtime, project_root=tmp_path)

        assert url == f"http://127.0.0.1:{port}"
        assert runtime.state("Applicaster").owner == kbctl.OWNER_ADOPTED


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.slow
def test_ensure_launches_a_real_instance_and_waits_until_its_api_answers(tmp_path):
    kb_dir = tmp_path / "kb"
    (kb_dir / "articles").mkdir(parents=True)
    (kb_dir / "categories").mkdir()
    runtime = kbctl.Runtime(state_dir=tmp_path / "run")
    kb = kbctl.KnowledgeBase(name="Scratch", port=free_port(), kb_dir=kb_dir)

    try:
        url = kbctl.ensure(kb, runtime, project_root=PROJECT_ROOT, timeout=90)

        assert urllib.request.urlopen(f"{url}/api/tags", timeout=5).status == 200
        state = runtime.state("Scratch")
        assert state.owner == kbctl.OWNER_KBCTL
        assert _pid_is_alive(state.pid)
    finally:
        kbctl.stop(kb.name, runtime)

    assert kbctl.is_listening(kb.port) is False
    assert runtime.state("Scratch") is None


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_stop_refuses_to_kill_an_instance_it_did_not_start(tmp_path):
    """Guards against pid 0 reaching killpg, which would signal our own group."""
    runtime = kbctl.Runtime(state_dir=tmp_path)
    runtime.record_start("Applicaster", pid=0, port=8004, owner=kbctl.OWNER_ADOPTED)

    with pytest.raises(kbctl.KbctlError, match="started outside kbctl"):
        kbctl.stop("Applicaster", runtime)

    assert runtime.state("Applicaster") is not None


def test_launch_command_disables_reload_so_source_edits_do_not_drop_mcp_sessions():
    kb = kbctl.KnowledgeBase(name="Applicaster", port=8004, kb_dir=Path("/tmp/akb"))

    assert kbctl.launch_command(kb) == [
        "uv", "run", "python", "run.py", "--port=8004", "--no-reload", "--kb-dir=/tmp/akb",
    ]


def test_launch_command_omits_kb_dir_for_the_bundled_knowledge_base():
    kb = kbctl.KnowledgeBase(name="self", port=8001, kb_dir=None)

    assert kbctl.launch_command(kb) == [
        "uv", "run", "python", "run.py", "--port=8001", "--no-reload",
    ]


@contextlib.contextmanager
def idle_instance(runtime, name="Scratch", **state):
    """A registered instance backed by a real, killable process."""
    process = subprocess.Popen(["sleep", "600"], start_new_session=True)
    runtime.record_start(
        name, pid=process.pid, port=free_port(), owner=kbctl.OWNER_KBCTL, **state
    )
    try:
        yield process
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        process.wait()


def test_reap_stops_an_instance_that_nobody_is_using(tmp_path):
    runtime = kbctl.Runtime(state_dir=tmp_path)
    with idle_instance(runtime) as process:
        kbctl.reap("Scratch", runtime, after=0)

        assert process.poll() is not None
        assert runtime.state("Scratch") is None


def test_reap_backs_off_when_a_session_reclaimed_the_instance_while_it_waited(tmp_path):
    runtime = kbctl.Runtime(state_dir=tmp_path)
    with idle_instance(runtime) as process:
        runtime.acquire_lease("Scratch", pid=os.getpid())

        kbctl.reap("Scratch", runtime, after=0)

        assert process.poll() is None
        assert runtime.state("Scratch") is not None


def test_scheduled_reap_runs_detached_and_stops_the_instance_later(tmp_path):
    runtime = kbctl.Runtime(state_dir=tmp_path)
    with idle_instance(runtime) as process:
        kbctl.schedule_reap("Scratch", runtime, after=0.5)

        deadline = time.monotonic() + 20
        while process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.2)

        assert process.poll() is not None, "detached reaper never stopped the instance"


def run_cli(*args, config: Path | None = None, state_dir: Path | None = None):
    argv = [sys.executable, "-m", "wikiknowledge.tools.kbctl"]
    if config is not None:
        argv += ["--config", str(config)]
    if state_dir is not None:
        argv += ["--state-dir", str(state_dir)]
    return subprocess.run(
        argv + list(args), cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=60
    )


def test_doctor_fails_and_names_the_knowledge_base_whose_directory_is_gone(tmp_path):
    config = write_config(tmp_path, {"KADS": {"kb_dir": "./gone", "port": 8002}})

    result = run_cli("doctor", config=config, state_dir=tmp_path / "run")

    assert result.returncode == 1
    assert "KADS" in result.stdout


def test_doctor_succeeds_on_a_healthy_config(tmp_path):
    (tmp_path / "kb").mkdir()
    config = write_config(tmp_path, {"Fine": {"kb_dir": "./kb", "port": 8006}})

    result = run_cli("doctor", config=config, state_dir=tmp_path / "run")

    assert result.returncode == 0


def test_list_shows_each_configured_knowledge_base_with_its_port(tmp_path):
    (tmp_path / "kb").mkdir()
    config = write_config(tmp_path, {"Applicaster": {"kb_dir": "./kb", "port": 8004}})

    result = run_cli("list", config=config, state_dir=tmp_path / "run")

    assert result.returncode == 0
    assert "Applicaster" in result.stdout and "8004" in result.stdout


def test_url_prints_the_mcp_endpoint_a_client_should_connect_to(tmp_path):
    (tmp_path / "kb").mkdir()
    config = write_config(tmp_path, {"Applicaster": {"kb_dir": "./kb", "port": 8004}})

    result = run_cli("url", "Applicaster", "--mcp", config=config, state_dir=tmp_path / "run")

    assert result.stdout.strip() == "http://127.0.0.1:8004/mcp/sse/"


def test_up_fails_cleanly_when_the_knowledge_base_directory_is_missing(tmp_path):
    config = write_config(tmp_path, {"KADS": {"kb_dir": "./gone", "port": 8002}})

    result = run_cli("up", "KADS", config=config, state_dir=tmp_path / "run")

    assert result.returncode == 1
    assert "does not exist" in result.stderr


def test_unknown_knowledge_base_is_rejected_with_the_available_names(tmp_path):
    (tmp_path / "kb").mkdir()
    config = write_config(tmp_path, {"Applicaster": {"kb_dir": "./kb", "port": 8004}})

    result = run_cli("up", "Typo", config=config, state_dir=tmp_path / "run")

    assert result.returncode == 1
    assert "Applicaster" in result.stderr


def test_kbctl_wrapper_runs_from_any_working_directory(tmp_path):
    (tmp_path / "kb").mkdir()
    config = write_config(tmp_path, {"Applicaster": {"kb_dir": "./kb", "port": 8004}})

    result = subprocess.run(
        [str(PROJECT_ROOT / "tools" / "kbctl"), "--config", str(config),
         "--state-dir", str(tmp_path / "run"), "list"],
        cwd="/", capture_output=True, text=True, timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert "Applicaster" in result.stdout


def test_kb_mcp_wrapper_runs_from_any_working_directory(tmp_path):
    (tmp_path / "kb").mkdir()
    config = write_config(tmp_path, {"Applicaster": {"kb_dir": "./kb", "port": 8004}})

    result = subprocess.run(
        [str(PROJECT_ROOT / "tools" / "kb-mcp"), "--config", str(config),
         "--state-dir", str(tmp_path / "run"), "Typo"],
        cwd="/", capture_output=True, text=True, timeout=60,
    )

    assert result.returncode == 1
    assert "unknown knowledge base" in result.stderr


@pytest.mark.slow
def test_instance_serves_its_own_knowledge_base_not_the_bundled_one(tmp_path):
    kb_dir = tmp_path / "kb"
    (kb_dir / "articles").mkdir(parents=True)
    (kb_dir / "categories").mkdir()
    (kb_dir / "articles" / "only-here.md").write_text(
        "---\nid: only-here\ntitle: Only Here\ntype: leaf\ntags: []\ncategories: []\n---\n\nMarker.\n"
    )
    runtime = kbctl.Runtime(state_dir=tmp_path / "run")
    kb = kbctl.KnowledgeBase(name="Scratch", port=free_port(), kb_dir=kb_dir)

    try:
        url = kbctl.ensure(kb, runtime, project_root=PROJECT_ROOT, timeout=90)
        with urllib.request.urlopen(f"{url}/api/articles", timeout=10) as response:
            ids = {article["id"] for article in json.load(response)}

        assert "only-here" in ids
        assert "ai-interaction-guide" not in ids, "the bundled knowledge base leaked in"
    finally:
        kbctl.stop(kb.name, runtime)


def count_reapers(name: str) -> int:
    listing = subprocess.run(["/bin/ps", "-Ao", "command"], capture_output=True, text=True).stdout
    return sum(
        1 for line in listing.splitlines()
        if "wikiknowledge.tools.kbctl" in line and f"reap {name}" in line
    )


def test_reap_waits_out_a_deadline_that_moved_while_it_was_sleeping(tmp_path):
    """A client that used the instance and left again pushes the deadline out."""
    runtime = kbctl.Runtime(state_dir=tmp_path)
    with idle_instance(runtime) as process:
        runtime.set_idle_deadline("Scratch", time.time() + 1.0)

        started = time.monotonic()
        kbctl.reap("Scratch", runtime, after=0)

        assert time.monotonic() - started >= 1.0, "reaper ignored the extended deadline"
        assert process.poll() is not None


def test_scheduling_twice_leaves_a_single_pending_reaper(tmp_path):
    runtime = kbctl.Runtime(state_dir=tmp_path)
    with idle_instance(runtime):
        try:
            kbctl.schedule_reap("Scratch", runtime, after=60)
            kbctl.schedule_reap("Scratch", runtime, after=60)
            kbctl.schedule_reap("Scratch", runtime, after=60)

            deadline = time.monotonic() + 10
            while count_reapers("Scratch") == 0 and time.monotonic() < deadline:
                time.sleep(0.2)
            time.sleep(1.0)

            assert count_reapers("Scratch") == 1
        finally:
            subprocess.run(["/usr/bin/pkill", "-f", "wikiknowledge.tools.kbctl.*reap Scratch"])


def test_a_second_reaper_is_scheduled_once_the_first_has_finished(tmp_path):
    runtime = kbctl.Runtime(state_dir=tmp_path)
    with idle_instance(runtime):
        runtime.record_reaper("Scratch", pid=DEAD_PID)

        assert runtime.reaper_alive("Scratch") is False


def test_signalling_a_group_still_reaches_it_after_its_leader_has_exited(tmp_path):
    """The recorded pid is the launcher, and the launcher exits first — `uv` hands
    off to the server and goes. What has to be killed is what it left behind, in
    the same group, and looking the group up from a pid that is already gone
    finds nothing."""
    leader = subprocess.Popen(
        ["sh", "-c", "sleep 600 & echo $!; exit 0"],
        stdout=subprocess.PIPE, text=True, start_new_session=True,
    )
    survivor = int(leader.stdout.readline())
    leader.wait()

    try:
        assert os.getpgid(survivor) == leader.pid, "survivor left the group; test is wrong"

        kbctl._signal_group(leader.pid, signal.SIGKILL)

        deadline = time.monotonic() + 5
        while _pid_is_alive(survivor) and time.monotonic() < deadline:
            time.sleep(0.1)
        assert not _pid_is_alive(survivor), "the signal never reached the group"
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.kill(survivor, signal.SIGKILL)
