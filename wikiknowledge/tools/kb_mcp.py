"""MCP stdio shim (kb-mcp)

:wk-id: kb-mcp
:wk-tags: architecture, mcp, sse, integration, cli
:wk-categories: system-architecture

`kb-mcp` presents a knowledge base to an MCP client as an ordinary stdio server.
The client spawns it instead of connecting to the instance directly, which
matters because a client resolves its MCP servers once, when a session opens: an
instance that happens to be stopped at that moment would be marked unavailable
for the rest of the session. Spawning a shim always succeeds, and the shim takes
responsibility for getting the instance up.

## What it does

1. Asks [[src:wikiknowledge/kbctl|kbctl]] to `ensure` the instance — starting it
   and waiting for its API if it was not already serving.
2. Takes a lease, so the idle reaper leaves the instance alone while a client is
   attached.
3. Opens the instance's SSE transport at `/mcp/sse/` and reads the `endpoint`
   event to learn where to POST.
4. Relays frames: stdin lines are POSTed to that endpoint, and `message` events
   from the stream are written to stdout.
5. On disconnect, releases its lease and — if it was the last client — schedules
   the idle countdown.

The relay never inspects the frames it carries, so tools added to the MCP server
need no change here.

## Registering it

```json
{
  "mcpServers": {
    "kb-applicaster": {
      "command": "/path/to/WikiKnowledge/tools/kb-mcp",
      "args": ["Applicaster"]
    }
  }
}
```

## Stream discipline

stdout carries protocol frames and nothing else; diagnostics go to stderr. A
stray print to stdout would corrupt the JSON-RPC stream.
"""

from __future__ import annotations

import argparse
import contextlib
import http.client
import os
import sys
import threading
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterator

from wikiknowledge.tools import kbctl

CONNECT_TIMEOUT = 15.0


def log(message: str) -> None:
    """Diagnostics go to stderr. stdout carries protocol frames only."""
    print(f"kb-mcp: {message}", file=sys.stderr, flush=True)


def _open_event_stream(base: str) -> http.client.HTTPResponse:
    parts = urllib.parse.urlparse(base)
    connection = http.client.HTTPConnection(parts.hostname, parts.port, timeout=CONNECT_TIMEOUT)
    connection.request("GET", "/mcp/sse/", headers={"Accept": "text/event-stream"})
    response = connection.getresponse()
    if response.status != 200:
        raise kbctl.KbctlError(f"SSE endpoint answered HTTP {response.status}")
    # The stream stays open for the whole session, so it must not time out
    # while the client is simply idle.
    connection.sock.settimeout(None)
    return response


def _events(response: http.client.HTTPResponse) -> Iterator[tuple[str, str]]:
    """Yield (event, data) pairs from a text/event-stream body."""
    event, data = None, []
    while True:
        raw = response.readline()
        if not raw:
            return
        line = raw.decode("utf-8", "replace").rstrip("\r\n")
        if line == "":
            if data:
                yield event or "message", "\n".join(data)
            event, data = None, []
        elif line.startswith(":"):
            continue  # keep-alive comment
        else:
            field, _, value = line.partition(":")
            value = value[1:] if value.startswith(" ") else value
            if field == "event":
                event = value
            elif field == "data":
                data.append(value)


def _post(url: str, payload: str) -> None:
    request = urllib.request.Request(
        url, data=payload.encode("utf-8"), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=CONNECT_TIMEOUT):
        pass


def _pump_to_stdout(events: Iterator[tuple[str, str]]) -> None:
    for event, data in events:
        if event == "message":
            sys.stdout.write(data + "\n")
            sys.stdout.flush()


def relay(base: str) -> None:
    """Move frames between stdio and the instance until either side hangs up."""
    response = _open_event_stream(base)
    events = _events(response)

    post_url = None
    for event, data in events:
        if event == "endpoint":
            post_url = urllib.parse.urljoin(base, data)
            break
    if post_url is None:
        raise kbctl.KbctlError("instance closed the stream before advertising an endpoint")

    reader = threading.Thread(target=_pump_to_stdout, args=(events,), daemon=True)
    reader.start()

    for line in sys.stdin:
        frame = line.strip()
        if frame:
            _post(post_url, frame)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kb-mcp", description="Serve a WikiKnowledge knowledge base over stdio MCP."
    )
    parser.add_argument("name", help="knowledge base name from config.json")
    parser.add_argument("--config", type=Path, default=kbctl.DEFAULT_CONFIG)
    parser.add_argument("--state-dir", type=Path, default=kbctl.DEFAULT_STATE_DIR)
    parser.add_argument(
        "--idle",
        type=float,
        default=kbctl.DEFAULT_IDLE_TIMEOUT,
        help="seconds to leave the instance running after the last client leaves",
    )
    args = parser.parse_args(argv)

    runtime = kbctl.Runtime(state_dir=args.state_dir)
    try:
        kbs = kbctl.load_config(args.config)
        kb = kbs[args.name] if args.name in kbs else None
        if kb is None:
            raise kbctl.KbctlError(
                f"unknown knowledge base {args.name!r}; configured: {', '.join(sorted(kbs))}"
            )
        base = kbctl.ensure(kb, runtime, kbctl.PROJECT_ROOT)
    except (kbctl.KbctlError, FileNotFoundError) as error:
        log(str(error))
        return 1

    runtime.acquire_lease(kb.name, os.getpid())
    try:
        relay(base)
    except kbctl.KbctlError as error:
        log(str(error))
        return 1
    except (BrokenPipeError, KeyboardInterrupt):
        pass
    finally:
        runtime.release_lease(kb.name, os.getpid())
        if not runtime.lease_holders(kb.name):
            with contextlib.suppress(OSError):
                kbctl.schedule_reap(kb.name, runtime, after=args.idle)
    return 0


if __name__ == "__main__":
    sys.exit(main())
