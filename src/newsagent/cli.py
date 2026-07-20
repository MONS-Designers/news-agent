"""Operator CLI for tasks that must work without a signed-in admin,
e.g. bootstrapping the first admin account.

Usage:
    python -m newsagent.cli add-admin you@example.com
    python -m newsagent.cli add-user you@example.com --name "Full Name"
"""

import argparse

from newsagent.db import SessionLocal
from newsagent.llm import get_llm_provider
from newsagent.mail import get_email_sender
from newsagent.pipeline import digest, fetcher, relevance, send, summarize
from newsagent.services import identity, preferences, sources


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
    subparsers.add_parser("filter", help="Score pending articles for relevance to their topic")
    subparsers.add_parser("summarize", help="Summarize + translate relevant articles to Hebrew")

    subscribe_cmd = subparsers.add_parser("subscribe", help="Subscribe a user to a topic")
    subscribe_cmd.add_argument("email")
    subscribe_cmd.add_argument("topic")

    subparsers.add_parser("build-digests", help="Build today's digests for all users")
    subparsers.add_parser("send-digests", help="Render and send all digests not yet sent")

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
        elif args.command == "filter":
            filter_report = relevance.filter_pending_articles(db, get_llm_provider())
            print(
                f"Scored {filter_report.scored}: {filter_report.relevant} relevant, "
                f"{filter_report.irrelevant} irrelevant "
                f"({filter_report.refused} refused, {filter_report.errors} errors, "
                f"{filter_report.borderline} borderline)"
            )
            print(
                f"Usage: {filter_report.usage_input_units} in / "
                f"{filter_report.usage_output_units} out units"
            )
        elif args.command == "summarize":
            summary_report = summarize.summarize_relevant_articles(db, get_llm_provider())
            print(
                f"Summarized {summary_report.summarized} "
                f"({summary_report.refused} refused, {summary_report.errors} errors)"
            )
            print(
                f"Usage: {summary_report.usage_input_units} in / "
                f"{summary_report.usage_output_units} out units"
            )
        elif args.command == "subscribe":
            try:
                _, created = preferences.subscribe(db, args.email, args.topic)
            except ValueError as error:
                print(f"Error: {error}")
                return 1
            print(f"{'Subscribed' if created else 'Already subscribed'}: {args.email} -> {args.topic}")
        elif args.command == "build-digests":
            digest_report = digest.build_digests(db, get_llm_provider())
            print(
                f"Users: {digest_report.users_processed}, "
                f"digests created: {digest_report.digests_created}, "
                f"articles added: {digest_report.articles_added}"
            )
        elif args.command == "send-digests":
            send_report = send.send_pending_digests(db, get_email_sender())
            print(f"Sent {send_report.sent}, failed {send_report.failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
