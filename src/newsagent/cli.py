"""Operator CLI for tasks that must work without a signed-in admin,
e.g. bootstrapping the first admin account.

Usage:
    python -m newsagent.cli add-admin you@example.com
    python -m newsagent.cli add-user you@example.com --name "Full Name"
"""

import argparse

from newsagent.db import SessionLocal
from newsagent.services import identity


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="newsagent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_admin = subparsers.add_parser("add-admin", help="Allow this email to access /admin")
    add_admin.add_argument("email")

    add_user = subparsers.add_parser("add-user", help="Allow this email to access /preferences")
    add_user.add_argument("email")
    add_user.add_argument("--name", default=None, help="Display name (optional)")

    args = parser.parse_args(argv)

    with SessionLocal() as db:
        if args.command == "add-admin":
            admin, created = identity.add_admin(db, args.email)
            print(f"{'Created' if created else 'Already exists'}: admin {admin.email} (id={admin.id})")
        elif args.command == "add-user":
            user, created = identity.add_user(db, args.email, args.name)
            print(f"{'Created' if created else 'Already exists'}: user {user.email} (id={user.id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
