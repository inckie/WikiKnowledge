"""Knowledge Base Control (kbctl)

:wk-id: kbctl
:wk-tags: architecture, manager, instances, cli, mcp
:wk-categories: system-architecture

`kbctl` is the command line counterpart to [[src:wikiknowledge/kb-manager|kb_manager.py]].
Where the Tkinter manager needs a human at the keyboard, `kbctl` can be driven by
scripts and by agents, and it is what [[src:wikiknowledge/kb-mcp|kb-mcp]] calls to
make sure an instance is serving before relaying a session to it.

Both read the same `config.json`, so the two can be used side by side.

## Commands

| Command | Purpose |
|---------|---------|
| `kbctl list` | every configured knowledge base, with port, status, owner and lease count |
| `kbctl status [name]` | the same view, narrowed to one instance |
| `kbctl doctor` | report configuration defects — missing directories, duplicate ports |
| `kbctl up <name> [--pin]` | start an instance and wait until its API answers |
| `kbctl ensure <name>` | print the base URL, starting the instance only if needed |
| `kbctl down <name>` | stop an instance |
| `kbctl restart <name>` | stop, then start again |
| `kbctl url <name> [--mcp]` | print the REST base URL, or the MCP SSE endpoint |
| `kbctl logs <name> [-n N] [-f]` | read an instance's log |
| `kbctl reap <name> --after S` | stop an instance once it has gone unused (internal) |

## Ownership

Every instance kbctl knows about is either **owned** or **adopted**. An instance
kbctl started is owned, and may be stopped automatically once nothing is using
it. An instance already serving when kbctl first looked — one launched from the
Tkinter manager, say — is adopted, and kbctl will never stop it on its own.
`--pin` marks an owned instance as exempt too.

## Idle shutdown

Clients register their interest by taking a *lease*: a file named after the
client's pid under `~/.wikiknowledge/run/<name>/leases/`. When the last lease is
dropped, the departing client hands a countdown to a detached `kbctl reap`
process. That process sleeps, re-checks, and stops the instance only if no lease
reappeared in the meantime — so a session that comes back during the window
keeps its instance alive. Leases whose process has died are swept on sight, so a
crashed client cannot pin an instance forever.

## Readiness

An open port is not readiness: uvicorn binds its socket before the lifespan has
finished parsing the knowledge base. kbctl therefore waits for `GET /api/tags`
to answer 200 before reporting an instance as up.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KnowledgeBase:
    """A knowledge base instance as declared in config.json."""

    name: str
    port: int
    kb_dir: Path | None


def load_config(config_path: Path) -> dict[str, KnowledgeBase]:
    """Read config.json, resolving kb_dir paths against the config's directory."""
    raw = json.loads(Path(config_path).read_text())
    base = Path(config_path).resolve().parent

    kbs: dict[str, KnowledgeBase] = {}
    for name, entry in raw.get("knowledge_bases", {}).items():
        kb_dir = entry.get("kb_dir") or ""
        kbs[name] = KnowledgeBase(
            name=name,
            port=int(entry["port"]),
            kb_dir=(base / kb_dir).resolve() if kb_dir else None,
        )
    return kbs


OWNER_KBCTL = "kbctl"
OWNER_ADOPTED = "adopted"


@dataclass(frozen=True)
class InstanceState:
    """What kbctl remembers about a running instance."""

    pid: int
    port: int
    owner: str
    pinned: bool


@dataclass(frozen=True)
class Problem:
    """A configuration defect found by `kbctl doctor`."""

    name: str
    kind: str
    detail: str


def diagnose(kbs: dict[str, KnowledgeBase]) -> list[Problem]:
    """Return configuration defects that would break a launch."""
    port_counts = Counter(kb.port for kb in kbs.values())

    problems: list[Problem] = []
    for kb in kbs.values():
        if kb.kb_dir is not None and not kb.kb_dir.is_dir():
            problems.append(Problem(kb.name, "missing-dir", f"{kb.kb_dir} does not exist"))
        if port_counts[kb.port] > 1:
            problems.append(Problem(kb.name, "duplicate-port", f"port {kb.port} is claimed twice"))
    return problems


def _pid_alive(pid: int) -> bool:
    """True if a process with this pid is still running.

    Reaps first: a child of ours that has exited but not been waited on is a
    zombie, and `os.kill(pid, 0)` happily reports a zombie as alive.
    """
    with contextlib.suppress(ChildProcessError, OSError):
        os.waitpid(pid, os.WNOHANG)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class Runtime:
    """Per-instance state on disk: pids, ports, logs and lease files."""

    def __init__(self, state_dir: Path) -> None:
        self.state_dir = Path(state_dir)

    def instance_dir(self, name: str) -> Path:
        return self.state_dir / name

    def _lease_dir(self, name: str) -> Path:
        return self.instance_dir(name) / "leases"

    def acquire_lease(self, name: str, pid: int) -> None:
        """Record that `pid` is actively using this knowledge base."""
        lease_dir = self._lease_dir(name)
        lease_dir.mkdir(parents=True, exist_ok=True)
        (lease_dir / str(pid)).touch()

    def release_lease(self, name: str, pid: int) -> None:
        """Drop a lease. Releasing a lease that is already gone is not an error."""
        (self._lease_dir(name) / str(pid)).unlink(missing_ok=True)

    def lease_holders(self, name: str) -> list[int]:
        """Live lease holders, sweeping away leases whose process has died."""
        lease_dir = self._lease_dir(name)
        if not lease_dir.is_dir():
            return []

        holders: list[int] = []
        for lease in lease_dir.iterdir():
            try:
                pid = int(lease.name)
            except ValueError:
                lease.unlink(missing_ok=True)
                continue
            if _pid_alive(pid):
                holders.append(pid)
            else:
                lease.unlink(missing_ok=True)
        return sorted(holders)

    def log_file(self, name: str) -> Path:
        return self.instance_dir(name) / "server.log"

    def _state_file(self, name: str) -> Path:
        return self.instance_dir(name) / "state.json"

    def record_start(
        self,
        name: str,
        pid: int,
        port: int,
        owner: str,
        pinned: bool = False,
    ) -> None:
        """Remember a running instance and who is responsible for it."""
        self.instance_dir(name).mkdir(parents=True, exist_ok=True)
        self._state_file(name).write_text(
            json.dumps({"pid": pid, "port": port, "owner": owner, "pinned": pinned})
        )

    def state(self, name: str) -> InstanceState | None:
        """Recorded state for an instance, or None if kbctl has never seen it."""
        try:
            raw = json.loads(self._state_file(name).read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return None
        return InstanceState(
            pid=int(raw["pid"]),
            port=int(raw["port"]),
            owner=raw.get("owner", OWNER_ADOPTED),
            pinned=bool(raw.get("pinned", False)),
        )

    def forget(self, name: str) -> None:
        """Drop recorded state after an instance has stopped."""
        self._state_file(name).unlink(missing_ok=True)

    def _deadline_file(self, name: str) -> Path:
        return self.instance_dir(name) / "idle_until"

    def set_idle_deadline(self, name: str, when: float) -> None:
        """Record the wall-clock time from which this instance may be stopped."""
        self.instance_dir(name).mkdir(parents=True, exist_ok=True)
        self._deadline_file(name).write_text(repr(when))

    def idle_deadline(self, name: str) -> float | None:
        try:
            return float(self._deadline_file(name).read_text())
        except (FileNotFoundError, ValueError):
            return None

    def _reaper_file(self, name: str) -> Path:
        return self.instance_dir(name) / "reaper.pid"

    def record_reaper(self, name: str, pid: int) -> None:
        self.instance_dir(name).mkdir(parents=True, exist_ok=True)
        self._reaper_file(name).write_text(str(pid))

    def reaper_alive(self, name: str) -> bool:
        """True if a reaper is already pending for this instance."""
        try:
            pid = int(self._reaper_file(name).read_text())
        except (FileNotFoundError, ValueError):
            return False
        if _pid_alive(pid):
            return True
        self._reaper_file(name).unlink(missing_ok=True)
        return False

    def clear_reaper(self, name: str) -> None:
        self._reaper_file(name).unlink(missing_ok=True)

    def should_reap(self, name: str) -> bool:
        """True only for an idle instance that kbctl started and nobody pinned."""
        state = self.state(name)
        if state is None or state.owner != OWNER_KBCTL or state.pinned:
            return False
        return not self.lease_holders(name)


DEFAULT_START_TIMEOUT = 120.0
READINESS_PATH = "/api/tags"


class KbctlError(RuntimeError):
    """A knowledge base could not be brought up or taken down."""


def base_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def sse_url(port: int) -> str:
    return f"{base_url(port)}/mcp/sse/"


def is_listening(port: int) -> bool:
    """True if anything holds the port, whether or not it speaks HTTP yet."""
    with socket.socket() as probe:
        probe.settimeout(0.25)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def _answers_api(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"{base_url(port)}{READINESS_PATH}", timeout=1.0) as response:
            return response.status == 200
    except Exception:
        return False


def wait_until_ready(port: int, timeout: float) -> bool:
    """Poll until the REST API answers. An open socket alone does not count:
    uvicorn binds before the lifespan has finished building the index."""
    deadline = time.monotonic() + timeout
    while True:
        if _answers_api(port):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.2)


def launch_command(kb: KnowledgeBase) -> list[str]:
    """The command that starts one background instance.

    Reload is off: a background instance reloading on a source edit would drop
    every live MCP session attached to it.
    """
    cmd = ["uv", "run", "python", "run.py", f"--port={kb.port}", "--no-reload"]
    if kb.kb_dir is not None:
        cmd.append(f"--kb-dir={kb.kb_dir}")
    return cmd


def _launch(kb: KnowledgeBase, project_root: Path, runtime: Runtime) -> int:
    if kb.kb_dir is not None and not kb.kb_dir.is_dir():
        raise KbctlError(f"{kb.name}: knowledge base directory {kb.kb_dir} does not exist")

    cmd = launch_command(kb)

    runtime.instance_dir(kb.name).mkdir(parents=True, exist_ok=True)
    log = runtime.log_file(kb.name).open("ab")
    process = subprocess.Popen(
        cmd,
        cwd=str(project_root),
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    return process.pid


def ensure(
    kb: KnowledgeBase,
    runtime: Runtime,
    project_root: Path,
    timeout: float = DEFAULT_START_TIMEOUT,
    pinned: bool = False,
) -> str:
    """Return the base URL of a serving instance, starting it if necessary."""
    if _answers_api(kb.port):
        if runtime.state(kb.name) is None:
            runtime.record_start(kb.name, pid=0, port=kb.port, owner=OWNER_ADOPTED, pinned=pinned)
        return base_url(kb.port)

    if is_listening(kb.port):
        # Something already holds the port — most likely an instance still
        # building its index. Give it the full budget before giving up.
        if wait_until_ready(kb.port, timeout=timeout):
            if runtime.state(kb.name) is None:
                runtime.record_start(kb.name, pid=0, port=kb.port, owner=OWNER_ADOPTED)
            return base_url(kb.port)
        raise KbctlError(f"{kb.name}: port {kb.port} is held by a process that never answered")

    pid = _launch(kb, project_root, runtime)
    runtime.record_start(kb.name, pid=pid, port=kb.port, owner=OWNER_KBCTL, pinned=pinned)

    if not wait_until_ready(kb.port, timeout=timeout):
        stop(kb.name, runtime)
        raise KbctlError(f"{kb.name}: did not answer within {timeout:g}s; see {runtime.log_file(kb.name)}")
    return base_url(kb.port)


def _signal_group(leader_pid: int, sig: int) -> None:
    """Signal the process group an instance was launched into.

    The group id is the launched pid itself: `_launch` uses
    `start_new_session=True`, which makes that process a session and group
    leader. Looking the group up with `getpgid` instead would work only while
    the leader is alive — and it is the first to go. `uv` hands off to the
    server and exits, so by the time an escalation is due, `getpgid` raises and
    the signal reaches nobody while the server is still holding the port.

    An already-empty group is not an error. BSD reports it as EPERM rather than
    ESRCH, so both are accepted, and callers must not read a delivered signal as
    success — they confirm the outcome by checking that the port was released.
    """
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(leader_pid, sig)


def _wait_until_gone(state: InstanceState, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while True:
        if not _pid_alive(state.pid) and not is_listening(state.port):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.2)


def stop(name: str, runtime: Runtime, grace: float = 10.0) -> None:
    """Terminate an instance kbctl started, then forget it."""
    state = runtime.state(name)
    if state is None:
        return
    if state.pid <= 0:
        raise KbctlError(f"{name}: started outside kbctl, stop it wherever it was launched")

    _signal_group(state.pid, signal.SIGTERM)
    if not _wait_until_gone(state, grace):
        _signal_group(state.pid, signal.SIGKILL)
        if not _wait_until_gone(state, 5.0):
            raise KbctlError(f"{name}: port {state.port} still held after SIGKILL")

    runtime.forget(name)


DEFAULT_IDLE_TIMEOUT = 900.0


def reap(name: str, runtime: Runtime, after: float = DEFAULT_IDLE_TIMEOUT) -> bool:
    """Wait out the idle window, then stop the instance if it is still unused.

    The deadline is re-read after every sleep. A client that used the instance
    and left again pushes it forward, so a reaper scheduled by an earlier
    disconnect cannot cut a later client's idle window short.
    """
    deadline = runtime.idle_deadline(name) or (time.time() + after)
    while True:
        remaining = deadline - time.time()
        if remaining > 0:
            time.sleep(remaining)
        moved = runtime.idle_deadline(name)
        if moved is not None and moved > deadline:
            deadline = moved
            continue
        break

    if not runtime.should_reap(name):
        return False
    stop(name, runtime)
    return True


def schedule_reap(name: str, runtime: Runtime, after: float = DEFAULT_IDLE_TIMEOUT) -> None:
    """Hand the idle countdown to a detached process, so the caller can exit.

    At most one reaper is pending per instance. A reaper already waiting will
    re-read the deadline we just wrote, so there is nothing for a second one to
    do. If the pending reaper happens to be on its way out as we look, the
    instance simply waits for the next disconnect to schedule a fresh one.
    """
    runtime.set_idle_deadline(name, time.time() + after)
    if runtime.reaper_alive(name):
        return

    runtime.instance_dir(name).mkdir(parents=True, exist_ok=True)
    log = runtime.log_file(name).open("ab")
    reaper = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "wikiknowledge.tools.kbctl",
            # Parent-parser options must precede the subcommand; argparse
            # rejects them afterwards.
            "--state-dir",
            str(runtime.state_dir),
            "reap",
            name,
            "--after",
            str(after),
        ],
        cwd=str(Path(__file__).resolve().parents[2]),
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    runtime.record_reaper(name, reaper.pid)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config.json"
DEFAULT_STATE_DIR = Path.home() / ".wikiknowledge" / "run"


def _pick(kbs: dict[str, KnowledgeBase], name: str) -> KnowledgeBase:
    try:
        return kbs[name]
    except KeyError:
        raise KbctlError(
            f"unknown knowledge base {name!r}; configured: {', '.join(sorted(kbs))}"
        ) from None


def _describe(kb: KnowledgeBase, runtime: Runtime) -> str:
    state = runtime.state(kb.name)
    if _answers_api(kb.port):
        status = "ready"
    elif is_listening(kb.port):
        status = "starting"
    else:
        status = "stopped"

    owner = state.owner if state else "-"
    if state and state.pinned:
        owner += "+pinned"
    leases = len(runtime.lease_holders(kb.name))
    where = kb.kb_dir if kb.kb_dir is not None else "(bundled)"
    return f"{kb.name:<16} {kb.port:<6} {status:<9} {owner:<16} leases={leases:<3} {where}"


def _cmd_list(args, kbs, runtime) -> int:
    for kb in kbs.values():
        print(_describe(kb, runtime))
    return 0


def _cmd_status(args, kbs, runtime) -> int:
    targets = [_pick(kbs, args.name)] if args.name else list(kbs.values())
    for kb in targets:
        print(_describe(kb, runtime))
    return 0


def _cmd_doctor(args, kbs, runtime) -> int:
    problems = diagnose(kbs)
    for problem in problems:
        print(f"{problem.name}: {problem.kind}: {problem.detail}")
    if not problems:
        print(f"{len(kbs)} knowledge base(s) configured, no problems found")
    return 1 if problems else 0


def _cmd_up(args, kbs, runtime) -> int:
    kb = _pick(kbs, args.name)
    print(ensure(kb, runtime, PROJECT_ROOT, timeout=args.timeout, pinned=args.pin))
    return 0


def _cmd_ensure(args, kbs, runtime) -> int:
    kb = _pick(kbs, args.name)
    print(ensure(kb, runtime, PROJECT_ROOT, timeout=args.timeout))
    return 0


def _cmd_down(args, kbs, runtime) -> int:
    stop(_pick(kbs, args.name).name, runtime)
    return 0


def _cmd_restart(args, kbs, runtime) -> int:
    kb = _pick(kbs, args.name)
    stop(kb.name, runtime)
    print(ensure(kb, runtime, PROJECT_ROOT, timeout=args.timeout))
    return 0


def _cmd_url(args, kbs, runtime) -> int:
    kb = _pick(kbs, args.name)
    print(sse_url(kb.port) if args.mcp else base_url(kb.port))
    return 0


def _cmd_logs(args, kbs, runtime) -> int:
    kb = _pick(kbs, args.name)
    log = runtime.log_file(kb.name)
    if not log.exists():
        raise KbctlError(f"{kb.name}: no log yet at {log}")

    with log.open() as handle:
        lines = handle.readlines()
        print("".join(lines[-args.lines :]), end="")
        if not args.follow:
            return 0
        while True:
            line = handle.readline()
            if line:
                print(line, end="", flush=True)
            else:
                time.sleep(0.3)


def _cmd_reap(args, kbs, runtime) -> int:
    try:
        reap(args.name, runtime, after=args.after)
    finally:
        runtime.clear_reaper(args.name)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kbctl", description="Start, stop and inspect WikiKnowledge instances."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    sub = parser.add_subparsers(dest="command", required=True)

    def with_name(name: str, help_text: str):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("name")
        return p

    sub.add_parser("list", help="show every configured knowledge base").set_defaults(func=_cmd_list)
    sub.add_parser("doctor", help="check the config for defects").set_defaults(func=_cmd_doctor)

    status = sub.add_parser("status", help="show one knowledge base, or all of them")
    status.add_argument("name", nargs="?")
    status.set_defaults(func=_cmd_status)

    up = with_name("up", "start a knowledge base and wait until it answers")
    up.add_argument("--pin", action="store_true", help="never stop this instance automatically")
    up.add_argument("--timeout", type=float, default=DEFAULT_START_TIMEOUT)
    up.set_defaults(func=_cmd_up)

    ensure_cmd = with_name("ensure", "print the base URL, starting the instance if needed")
    ensure_cmd.add_argument("--timeout", type=float, default=DEFAULT_START_TIMEOUT)
    ensure_cmd.set_defaults(func=_cmd_ensure)

    with_name("down", "stop a knowledge base").set_defaults(func=_cmd_down)

    restart = with_name("restart", "stop and start a knowledge base")
    restart.add_argument("--timeout", type=float, default=DEFAULT_START_TIMEOUT)
    restart.set_defaults(func=_cmd_restart)

    url = with_name("url", "print the REST base URL")
    url.add_argument("--mcp", action="store_true", help="print the MCP SSE endpoint instead")
    url.set_defaults(func=_cmd_url)

    logs = with_name("logs", "show an instance's log")
    logs.add_argument("-n", "--lines", type=int, default=50)
    logs.add_argument("-f", "--follow", action="store_true")
    logs.set_defaults(func=_cmd_logs)

    reap_cmd = with_name("reap", "stop an instance once it has been idle (internal)")
    reap_cmd.add_argument("--after", type=float, default=DEFAULT_IDLE_TIMEOUT)
    reap_cmd.set_defaults(func=_cmd_reap)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        kbs = load_config(args.config)
    except FileNotFoundError:
        print(f"kbctl: no config at {args.config}", file=sys.stderr)
        return 1

    runtime = Runtime(state_dir=args.state_dir)
    try:
        return args.func(args, kbs, runtime)
    except KbctlError as error:
        print(f"kbctl: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
