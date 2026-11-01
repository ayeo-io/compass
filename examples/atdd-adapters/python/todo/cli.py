"""The todo service's command line.

    python -m todo.cli --data-dir DATA account EMAIL
    python -m todo.cli --data-dir DATA add EMAIL NAME
    python -m todo.cli --data-dir DATA complete EMAIL NAME
    python -m todo.cli --data-dir DATA archive EMAIL NAME
    python -m todo.cli --data-dir DATA list EMAIL [--state open|completed|archived]

`list` prints one name a line. A refused request exits 1 and prints
`error: <reason>` on standard error.
"""
from __future__ import annotations

import argparse
import os
import sys

from todo.service import STATES, TodoError, TodoService


def main(argv=None):
    parser = argparse.ArgumentParser(prog="todo", description="The todo command line.")
    parser.add_argument("--data-dir", default=os.environ.get("TODO_DATA_DIR"),
                        help="the folder that holds the store (default: $TODO_DATA_DIR)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("account", help="create an account").add_argument("email")
    for name in ("add", "complete", "archive"):
        command = commands.add_parser(name, help=f"{name} a todo")
        command.add_argument("email")
        command.add_argument("name")
    listing = commands.add_parser("list", help="list the todos in one state")
    listing.add_argument("email")
    listing.add_argument("--state", choices=STATES, default="open")
    args = parser.parse_args(argv)
    if not args.data_dir:
        parser.error("give --data-dir or set TODO_DATA_DIR")

    service = TodoService(args.data_dir)
    try:
        if args.command == "account":
            service.create_account(args.email)
        elif args.command == "list":
            for name in service.todos(args.email, args.state):
                print(name)
        else:
            getattr(service, args.command)(args.email, args.name)
    except TodoError as refusal:
        print(f"error: {refusal}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
