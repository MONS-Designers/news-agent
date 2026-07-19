"""Operator CLI for tasks that must work without a signed-in admin,
e.g. bootstrapping the first admin account.

Usage:
    python -m newsagent.cli add-admin you@example.com
    python -m newsagent.cli add-user you@example.com --name "Full Name"
"""

import argparse

from newsagent.db import SessionLocal
from newsagent.pipeline import fetcher
from newsagent.services import identity, sources


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="newsagent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_admin = subparsers.add_parser("add-admin", help="Allow this email to access /admin")
    add_admin.add_argument("email")

    add_user = subparsers.add_parser("add-user", help="Allow this email to access /preferences")
    add_user.add_argument("email")
    add_user.add_argument("--name", default=None, help="Display name (optional)")

    subparsers.add_parser("seed-sources", help="Load the curated default topics + RSS sources")
    subparsers.add_parser("fetch", help="Fetch new articles from all approved sources")

    args = parser.parse_args(argv)

    with SessionLocal() as db:
        if args.command == "add-admin":
            admin, created = identity.add_admin(db, args.email)
            print(f"{'Created' if created else 'Already exists'}: admin {admin.email} (id={admin.id})")
        elif args.command == "add-user":
            user, created = identity.add_user(db, args.email, args.name)
            print(f"{'Created' if created else 'Already exists'}: user {user.email} (id={user.id})")
        elif args.command == "seed-sources":
            report = sources.seed_default_sources(db)
            print(f"Seeded: {report.topics_created} new topics, {report.sources_created} new sources")
        elif args.command == "fetch":
            fetch_report = fetcher.fetch_approved_sources(db)
            for result in fetch_report.results:
                status = f"ERROR: {result.error}" if result.error else (
                    f"{result.new_articles} new, {result.duplicates} known"
                )
                print(f"  {result.source_name}: {status}")
            print(f"Total new articles: {fetch_report.total_new}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
