"""blackbox — command-line client for a BlackBox API instance.

Talks HTTP to a running server (it is not an offline tool):

    blackbox list --robot W-104
    blackbox show INC-2026-0728-001
    blackbox upload flight.mcap --metadata '{"id": "INC-1", "robot_id": "W-1"}'
    blackbox replay incident.json --speed 10   # robot simulator over WS
    blackbox prune --days 90 --yes

Configuration: --api / BLACKBOX_API_URL (default http://localhost:8000)
and --token / BLACKBOX_API_TOKEN when the server has auth enabled.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


class CliError(Exception):
    """A user-facing failure; printed without a traceback."""


def _request(
    method: str,
    url: str,
    *,
    token: str | None = None,
    body: bytes | None = None,
    content_type: str | None = None,
) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(
        url, method=method, data=body, headers=headers
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise CliError(f"{method} {url} failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise CliError(f"cannot reach {url}: {exc.reason}") from exc
    result = json.loads(payload or b"{}")
    if not isinstance(result, dict):
        return {"items": result}
    return result


def _multipart(
    filename: str, data: bytes, metadata: str | None
) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts = [
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; '
            f'filename="{filename}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        + data
        + b"\r\n"
    ]
    if metadata:
        parts.append((
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="metadata"\r\n\r\n'
            f"{metadata}\r\n"
        ).encode())
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _cmd_list(args: argparse.Namespace) -> None:
    query: dict[str, str] = {"limit": str(args.limit)}
    if args.robot:
        query["robot_id"] = args.robot
    body = _request(
        "GET",
        f"{args.api}/api/incidents?{urllib.parse.urlencode(query)}",
        token=args.token,
    )
    rows = body.get("items", [])
    if not rows:
        print("no incidents")
        return
    print(f"{'ID':28} {'ROBOT':8} {'OUTCOME':10} {'CAUSE':24} CONF  TASK")
    for item in rows:
        category = item.get("failure_category") or "-"
        confidence = item.get("confidence")
        conf = f"{confidence:.0%}" if confidence is not None else "-"
        print(
            f"{item['id']:28} {item['robot_id']:8} {item['outcome']:10} "
            f"{category:24} {conf:5} {item['task_name'][:40]}"
        )
    print(f"({len(rows)} of {body.get('total', len(rows))} incidents)")


def _cmd_show(args: argparse.Namespace) -> None:
    body = _request(
        "GET",
        f"{args.api}/api/incidents/{urllib.parse.quote(args.id)}",
        token=args.token,
    )
    incident = body["incident"]
    analysis = body.get("analysis")
    print(f"{incident['id']} — {incident['task_name']}")
    print(
        f"  robot    {incident['robot_id']} ({incident['robot_model']}) "
        f"at {incident['facility']}"
    )
    print(
        f"  window   {incident['start_time']} → {incident['end_time']} "
        f"({incident['outcome']}, {incident['severity']})"
    )
    print(f"  summary  {incident['summary']}")
    if analysis:
        print(
            f"  cause    {analysis['failure_category']} "
            f"({analysis['confidence']:.0%} confidence)"
        )
        print(f"  because  {analysis['explanation']}")
        for item in analysis.get("evidence", []):
            print(f"    - t={item['t']:.1f}s {item['summary']}")
    feedback = body.get("feedback")
    if feedback:
        verdict = feedback["verdict"]
        actual = feedback.get("actual_category")
        suffix = f" (actually {actual})" if actual else ""
        print(f"  verdict  {verdict}{suffix}")


def _cmd_upload(args: argparse.Namespace) -> None:
    path = Path(args.file)
    if not path.is_file():
        raise CliError(f"no such file: {path}")
    body, content_type = _multipart(
        path.name, path.read_bytes(), args.metadata
    )
    result = _request(
        "POST",
        f"{args.api}/api/incidents/upload",
        token=args.token,
        body=body,
        content_type=content_type,
    )
    print(
        f"{result['incident_id']}: {result['failure_category']} "
        f"({result['confidence']:.0%} confidence, "
        f"{result['event_count']} events)"
    )


def _cmd_prune(args: argparse.Namespace) -> None:
    cutoff = args.before or (
        datetime.now(UTC) - timedelta(days=args.days)
    ).isoformat()
    if not args.yes:
        raise CliError(
            f"refusing to prune incidents before {cutoff} without --yes"
        )
    result = _request(
        "DELETE",
        f"{args.api}/api/incidents?"
        + urllib.parse.urlencode({"before": cutoff}),
        token=args.token,
    )
    print(f"deleted {result['deleted']} incident(s)")
    for incident_id in result.get("incident_ids", []):
        print(f"  - {incident_id}")


def incident_to_frames(incident: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert a canonical incident into streaming frames, time-ordered.

    Events keep their absolute timestamps; telemetry sample times are
    re-based from seconds-since-start to absolute unix time. If the
    incident has no terminal event (e.g. a successful baseline run), an
    explicit cut frame carrying the original id/outcome is appended so
    the server stores it under the same identity.
    """
    start_epoch = datetime.fromisoformat(
        incident["start_time"].replace("Z", "+00:00")
    ).timestamp()

    timed: list[tuple[float, int, dict[str, Any]]] = []
    terminal_seen = False
    for event in incident.get("events", []):
        t = datetime.fromisoformat(
            event["timestamp"].replace("Z", "+00:00")
        ).timestamp()
        if event["event_type"] in ("task_failed", "task_timed_out"):
            terminal_seen = True
        timed.append((t, 1, {
            "type": "event",
            "t": t,
            "event_type": event["event_type"],
            "subsystem": event["subsystem"],
            "severity": event.get("severity", "info"),
            "message": event["message"],
            "payload": event.get("payload", {}),
        }))
    for series in incident.get("telemetry", []):
        for sample in series["samples"]:
            t = start_epoch + sample["t"]
            timed.append((t, 0, {
                "type": "sample",
                "t": t,
                "channel": series["channel"],
                "value": sample["value"],
                "unit": series.get("unit", ""),
            }))
    timed.sort(key=lambda item: (item[0], item[1]))

    # The server cuts at the first terminal event; frames after it would
    # start a spurious second incident, so stop the replay there.
    if terminal_seen:
        for index, (_, _, frame) in enumerate(timed):
            if frame["type"] == "event" and frame["event_type"] in (
                "task_failed",
                "task_timed_out",
            ):
                timed = timed[: index + 1]
                break

    frames: list[dict[str, Any]] = [{
        "type": "hello",
        "meta": {
            key: incident[key]
            for key in (
                "robot_model", "facility", "task_name", "task_goal",
                "software_version", "map_version", "environment",
            )
            if incident.get(key)
        },
    }]
    frames.extend(frame for _, _, frame in timed)
    if not terminal_seen:
        frames.append({
            "type": "cut",
            "id": incident["id"],
            "outcome": incident.get("outcome", "failed"),
            "severity": incident.get("severity", "error"),
            "summary": incident.get("summary"),
        })
    return frames


def _cmd_replay(args: argparse.Namespace) -> None:
    try:
        from websockets.sync.client import connect as ws_connect
    except ImportError as exc:
        raise CliError(
            "replay needs the websockets package: pip install websockets"
        ) from exc

    incident = json.loads(Path(args.file).read_text())
    frames = incident_to_frames(incident)
    robot_id = args.robot_id or incident["robot_id"]

    ws_base = args.api.replace("http://", "ws://").replace(
        "https://", "wss://"
    )
    url = f"{ws_base}/api/stream/{urllib.parse.quote(robot_id)}"
    if args.token:
        url += f"?token={urllib.parse.quote(args.token)}"

    import time

    with ws_connect(url) as ws:
        ws.recv()  # ready frame
        previous_t: float | None = None
        for frame in frames:
            t = frame.get("t")
            if (
                args.speed > 0
                and isinstance(t, float)
                and previous_t is not None
            ):
                time.sleep(max(0.0, (t - previous_t) / args.speed))
            if isinstance(t, float):
                previous_t = t
            ws.send(json.dumps(frame))
        while True:
            reply = json.loads(ws.recv())
            if reply.get("type") == "incident":
                print(
                    f"stored {reply['incident_id']}: "
                    f"{reply['failure_category']} "
                    f"({reply['confidence']:.0%} confidence, "
                    f"{reply['event_count']} events)"
                )
                break
            if reply.get("type") == "error":
                raise CliError(f"server rejected the stream: {reply['detail']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="blackbox", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--api",
        default=os.environ.get("BLACKBOX_API_URL", "http://localhost:8000"),
    )
    parser.add_argument(
        "--token", default=os.environ.get("BLACKBOX_API_TOKEN")
    )
    sub = parser.add_subparsers(dest="command", required=True)

    list_cmd = sub.add_parser("list", help="list incidents")
    list_cmd.add_argument("--robot", default=None)
    list_cmd.add_argument("--limit", type=int, default=20)
    list_cmd.set_defaults(func=_cmd_list)

    show = sub.add_parser("show", help="show one incident and its diagnosis")
    show.add_argument("id")
    show.set_defaults(func=_cmd_show)

    upload = sub.add_parser(
        "upload", help="upload a .json/.csv/.mcap incident"
    )
    upload.add_argument("file")
    upload.add_argument("--metadata", default=None, help="metadata JSON")
    upload.set_defaults(func=_cmd_upload)

    prune = sub.add_parser("prune", help="delete incidents older than a cutoff")
    group = prune.add_mutually_exclusive_group(required=True)
    group.add_argument("--before", default=None, help="ISO cutoff time")
    group.add_argument("--days", type=int, help="cutoff = now - N days")
    prune.add_argument(
        "--yes", action="store_true", help="actually delete (required)"
    )
    prune.set_defaults(func=_cmd_prune)

    replay = sub.add_parser(
        "replay",
        help="stream a canonical incident JSON through the live "
        "WebSocket endpoint (a robot simulator for testing streaming)",
    )
    replay.add_argument("file")
    replay.add_argument(
        "--speed", type=float, default=0.0,
        help="replay pacing multiplier; 0 (default) sends immediately, "
        "10 replays at 10x real time",
    )
    replay.add_argument(
        "--robot-id", default=None, help="override the incident's robot id"
    )
    replay.set_defaults(func=_cmd_replay)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except CliError as exc:
        print(f"blackbox: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
