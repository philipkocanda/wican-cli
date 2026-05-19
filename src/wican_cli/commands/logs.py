"""wican logs — list, download, or query OBD log databases."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from wican_cli.client import WiCANClient, WiCANError, handle_client_error
from wican_cli.commands._common import get_client, positive_int


def _get_cached_log(client: WiCANClient, filename: str, *, force: bool = False) -> Path:
    """Download a log database with local caching.

    Databases are cached under ~/.cache/wican/logs/.  Active databases (still
    being written to) are always re-downloaded; inactive ones are only fetched
    once unless *force* is True.
    """
    cache_dir = Path.home() / ".cache" / "wican" / "logs"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / filename

    if cached.exists() and not force:
        return cached

    db_data = client.download_log(filename)
    cached.write_bytes(db_data)
    return cached


def _open_log_db(path: Path) -> sqlite3.Connection:
    """Open a log database read-only, tolerating partial corruption.

    If the database header is too damaged to open, the error is swallowed
    and the connection is returned anyway — allowing subsequent queries to
    attempt reads on whatever pages are still intact.
    """
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only = ON")
    except sqlite3.DatabaseError:
        pass
    return conn


def _resolve_log_target(
    client: WiCANClient, args: argparse.Namespace
) -> tuple[str, bool] | None:
    """Resolve the target database filename and whether it's active.

    Returns (filename, is_active) or None on failure (errors are printed).
    """
    try:
        data = client.list_logs()
    except WiCANError as e:
        handle_client_error(e)
        return None

    databases = data.get("databases", [])
    db_files = [db["filename"] for db in databases if db.get("filename", "").endswith(".db")]
    if not db_files:
        print("No .db files found on device.", file=sys.stderr)
        sys.exit(1)

    target = args.db if args.db else db_files[-1]
    if args.db and args.db not in db_files:
        print(f"ERROR: Database '{args.db}' not found on device.", file=sys.stderr)
        print(f"  Available: {', '.join(db_files)}", file=sys.stderr)
        sys.exit(1)

    current_db = data.get("current_db", "")
    is_active = target == current_db
    return target, is_active


def _cmd_logs_list(client: WiCANClient, args: argparse.Namespace) -> None:
    """List available log databases."""
    try:
        data = client.list_logs()
    except WiCANError as e:
        handle_client_error(e)
        return

    databases = data.get("databases", [])

    if args.json:
        print(json.dumps(data, indent=2))
    else:
        if not databases:
            print("No log files found on device.")
        else:
            current = data.get("current_db", "")
            print(f"Log databases ({len(databases)}):")
            for db in databases:
                name = db.get("filename", "?")
                created = db.get("created", "")
                size = db.get("size", 0)
                status = db.get("status", "")
                marker = " *" if name == current else ""
                print(f"  {name}  {created}  {size} bytes  [{status}]{marker}")


def _cmd_logs_download(client: WiCANClient, args: argparse.Namespace) -> None:
    """Download log databases from the device."""
    logs_dir = Path.cwd() / "logs"
    logs_dir.mkdir(exist_ok=True)

    try:
        data = client.list_logs()
    except WiCANError as e:
        handle_client_error(e)
        return

    databases = data.get("databases", [])
    filenames = [db["filename"] for db in databases if "filename" in db]

    if args.db:
        filenames = [f for f in filenames if f == args.db]
        if not filenames:
            print(f"ERROR: File '{args.db}' not found on device.", file=sys.stderr)
            sys.exit(1)

    for filename in filenames:
        dest = (logs_dir / filename).resolve()
        if not dest.is_relative_to(logs_dir.resolve()):
            print(f"  Skip {filename} (unsafe path)", file=sys.stderr)
            continue
        if dest.exists() and not args.force:
            print(f"  Skip {filename} (exists, use --force to overwrite)")
            continue
        print(f"  Downloading {filename}...", end=" ", flush=True)
        try:
            content = client.download_log(filename)
        except WiCANError as e:
            print(f"FAILED: {e}")
            continue
        with open(dest, "wb") as f:
            f.write(content)
        print(f"OK ({len(content)} bytes)")


def _cmd_logs_query(client: WiCANClient, args: argparse.Namespace) -> None:
    """Query a parameter from the latest log database."""
    resolved = _resolve_log_target(client, args)
    if resolved is None:
        return
    target, is_active = resolved

    try:
        db_path = _get_cached_log(client, target, force=is_active)
    except WiCANError as e:
        handle_client_error(e)
        return

    conn = _open_log_db(db_path)
    rows: list[tuple] = []

    # Tier 1: ideal query with JOIN + ORDER BY DESC (newest first)
    try:
        cursor = conn.execute(
            """
            SELECT d.timestamp, d.value
            FROM param_data d
            JOIN param_info i ON i.Id = d.param_id
            WHERE i.Name = ?
            ORDER BY d.timestamp DESC
            LIMIT ?
            """,
            (args.query, args.limit),
        )
        rows = cursor.fetchall()
    except sqlite3.DatabaseError:
        # Tier 2: resolve param_id separately, full table scan bypassing corrupt indexes
        try:
            pid_row = conn.execute(
                "SELECT Id FROM param_info WHERE Name = ?", (args.query,)
            ).fetchone()
            if pid_row:
                cursor = conn.execute(
                    "SELECT timestamp, value FROM param_data NOT INDEXED"
                    " WHERE param_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (pid_row[0], args.limit),
                )
                rows = cursor.fetchall()
                if rows:
                    print(
                        "NOTE: Database partially corrupt, results from table scan",
                        file=sys.stderr,
                    )
        except sqlite3.DatabaseError as e:
            # Tier 3: completely unreadable
            print(f"ERROR: Database too corrupt to query: {e}", file=sys.stderr)
            conn.close()
            sys.exit(1)

    conn.close()

    if not rows:
        print(f"No data found for parameter '{args.query}' in {target}")
        return

    if args.json:
        print(
            json.dumps(
                [
                    {"timestamp": datetime.fromtimestamp(ts).isoformat(), "value": val}
                    for ts, val in rows
                ],
                indent=2,
            )
        )
    else:
        print(f"Parameter: {args.query} (from {target}, last {len(rows)} values)")
        for ts, val in rows:
            dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
            print(f"  {dt}  {val}")


def _cmd_logs_params(client: WiCANClient, args: argparse.Namespace) -> None:
    """List all logged parameter names."""
    resolved = _resolve_log_target(client, args)
    if resolved is None:
        return
    target, is_active = resolved

    try:
        db_path = _get_cached_log(client, target, force=is_active)
    except WiCANError as e:
        handle_client_error(e)
        return

    conn = _open_log_db(db_path)

    try:
        cursor = conn.execute("SELECT Name FROM param_info ORDER BY Name")
        params = [row[0] for row in cursor.fetchall()]
    except sqlite3.DatabaseError:
        # Fallback: try without ORDER BY in case index is corrupt
        try:
            cursor = conn.execute("SELECT Name FROM param_info")
            params = sorted(row[0] for row in cursor.fetchall())
            print("NOTE: Database partially corrupt, results may be incomplete", file=sys.stderr)
        except sqlite3.DatabaseError as e:
            print(f"ERROR: Database too corrupt to read parameters: {e}", file=sys.stderr)
            conn.close()
            sys.exit(1)

    conn.close()

    if args.json:
        print(json.dumps(params, indent=2))
    else:
        print(f"Logged parameters ({len(params)}, from {target}):")
        for p in params:
            print(f"  {p}")


def cmd_logs(args: argparse.Namespace) -> None:
    """List, download, or query OBD log databases."""
    try:
        client = get_client(args)
    except WiCANError as e:
        handle_client_error(e)
        return

    if args.download:
        _cmd_logs_download(client, args)
    elif args.query:
        _cmd_logs_query(client, args)
    elif args.params:
        _cmd_logs_params(client, args)
    else:
        _cmd_logs_list(client, args)


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the logs subcommand."""
    p = subparsers.add_parser("logs", help="List, download, or query OBD log databases")
    p.add_argument(
        "--download", action="store_true", help="Download log databases to logs/ directory"
    )
    p.add_argument("--db", metavar="FILE", help="Specific database filename")
    p.add_argument("--force", action="store_true", help="Overwrite existing files on download")
    p.add_argument("--params", action="store_true", help="List all logged parameters")
    p.add_argument("--query", metavar="PARAM", help="Query a parameter (e.g. SOC_BMS)")
    p.add_argument(
        "--limit", type=positive_int, default=10, help="Number of rows to return (default: 10)"
    )
    p.add_argument("--json", action="store_true", help="JSON output")
    p.set_defaults(func=cmd_logs)
