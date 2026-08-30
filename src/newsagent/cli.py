"""Operator CLI for tasks that must work without a signed-in admin,
e.g. bootstrapping the first admin account.

Usage:
    python -m newsagent.cli add-admin you@example.com
    python -m newsagent.cli add-user you@example.com --name "Full Name"
"""

import argparse
import logging

import httpx
from sqlalchemy import case, func, select

from newsagent.db import SessionLocal
from newsagent.llm import get_llm_provider
from newsagent.logging_setup import attach_outbound_run, configure_logging, track_outbound_run_logs
from newsagent.mail import get_email_sender
from newsagent.models import OutboundCall
from newsagent.pipeline import digest, extract, fetcher, relevance, send, summarize
from newsagent.services import identity, preferences, sources, taxonomy
from newsagent.telemetry import STATUS_AVOIDED, STATUS_MALFORMED
from newsagent.telemetry import pricing as pricing_service


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(prog="newsagent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_admin = subparsers.add_parser("add-admin", help="Allow this email to access /admin")
    add_admin.add_argument("email")

    add_user = subparsers.add_parser("add-user", help="Allow this email to access /preferences")
    add_user.add_argument("email")
    add_user.add_argument("--name", default=None, help="Display name (optional)")

    subparsers.add_parser("seed-sources", help="Load the curated default topics + RSS sources")
    subparsers.add_parser("seed-fields", help="Load the curated default profile Fields")
    subparsers.add_parser("seed-roles", help="Load the curated default profile Roles per Field")
    subparsers.add_parser("fetch", help="Fetch new articles from all approved sources")
    subparsers.add_parser("filter", help="Score pending articles for relevance to their topic")
    subparsers.add_parser("summarize", help="Summarize + translate relevant articles to Hebrew")
    subparsers.add_parser(
        "extract", help="Fetch + extract full article text for relevant articles"
    )

    subscribe_cmd = subparsers.add_parser("subscribe", help="Subscribe a user to a topic")
    subscribe_cmd.add_argument("email")
    subscribe_cmd.add_argument("topic")

    subparsers.add_parser(
        "usage-report", help="Print LLM token usage, latency, and waste totals per purpose"
    )
    subparsers.add_parser(
        "refresh-pricing", help="Fetch current model $/Mtok rates and add any that changed"
    )

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
        elif args.command == "seed-fields":
            field_report = taxonomy.seed_default_fields(db)
            print(f"Seeded: {field_report.fields_created} new fields")
        elif args.command == "seed-roles":
            role_report = taxonomy.seed_default_roles(db)
            print(
                f"Seeded: {role_report.fields_created} new fields, "
                f"{role_report.roles_created} new roles"
            )
        elif args.command == "fetch":
            fetch_report = fetcher.fetch_approved_sources(db)
            for result in fetch_report.results:
                status = f"ERROR: {result.error}" if result.error else (
                    f"{result.new_articles} new, {result.duplicates} known"
                )
                print(f"  {result.source_name}: {status}")
            print(f"Total new articles: {fetch_report.total_new}")
        elif args.command == "filter":
            with track_outbound_run_logs():
                filter_report = relevance.filter_pending_articles(db, get_llm_provider())
                print(
                    f"Scored {filter_report.scored}: {filter_report.relevant} relevant, "
                    f"{filter_report.irrelevant} irrelevant "
                    f"({filter_report.refused} refused, {filter_report.errors} errors, "
                    f"{filter_report.borderline} borderline)"
                )
                if filter_report.run_id is not None:
                    try:
                        attach_outbound_run(db, filter_report.run_id)
                    except Exception:
                        logging.getLogger(__name__).warning(
                            "Failed to attach outbound_run_id=%s to its log entries",
                            filter_report.run_id,
                            exc_info=True,
                        )
        elif args.command == "summarize":
            with track_outbound_run_logs():
                summary_report = summarize.summarize_relevant_articles(db, get_llm_provider())
                print(
                    f"Summarized {summary_report.summarized} "
                    f"({summary_report.refused} refused, {summary_report.errors} errors)"
                )
                if summary_report.run_id is not None:
                    try:
                        attach_outbound_run(db, summary_report.run_id)
                    except Exception:
                        logging.getLogger(__name__).warning(
                            "Failed to attach outbound_run_id=%s to its log entries",
                            summary_report.run_id,
                            exc_info=True,
                        )
        elif args.command == "extract":
            extract_report = extract.extract_relevant_articles(db)
            print(f"Extracted {extract_report.extracted}, failed {extract_report.failed}")
        elif args.command == "usage-report":
            # Tokens + latency per purpose, straight from outbound_calls - the
            # atom-level table is the only source of truth (AD-13); no dollars,
            # since no pricing lookup is implemented yet (deferred-work.md).
            # The duration average excludes `avoided` rows - a cache hit's
            # near-zero lookup time would otherwise drag down the average of
            # real LLM call latencies for the same purpose (round 2 review
            # finding). `call_count` still includes them.
            real_duration_ms = case(
                (OutboundCall.status != STATUS_AVOIDED, OutboundCall.duration_ms)
            )
            rows = db.execute(
                select(
                    OutboundCall.purpose,
                    func.count(OutboundCall.id),
                    func.sum(OutboundCall.tokens_in),
                    func.sum(OutboundCall.tokens_out),
                    func.avg(real_duration_ms),
                )
                .group_by(OutboundCall.purpose)
                .order_by(OutboundCall.purpose)
            ).all()
            if not rows:
                print("No outbound calls recorded yet.")
            else:
                print("Usage by purpose:")
                for purpose, call_count, tokens_in, tokens_out, avg_duration_ms in rows:
                    avg_ms = f"{avg_duration_ms:.0f}" if avg_duration_ms is not None else "n/a"
                    print(
                        f"  {purpose}: {call_count} calls, "
                        f"{tokens_in or 0} in / {tokens_out or 0} out tokens, "
                        f"avg {avg_ms}ms (excl. avoided)"
                    )
            retried = db.scalar(
                select(func.count(OutboundCall.id)).where(OutboundCall.attempt > 1)
            ) or 0
            avoided = db.scalar(
                select(func.count(OutboundCall.id)).where(OutboundCall.status == STATUS_AVOIDED)
            ) or 0
            malformed = db.scalar(
                select(func.count(OutboundCall.id)).where(OutboundCall.status == STATUS_MALFORMED)
            ) or 0
            print(
                f"Waste: {retried} retried attempts, {avoided} avoided (cache-hit) calls, "
                f"{malformed} malformed (billed but unusable) calls"
            )
        elif args.command == "refresh-pricing":
            # Exit codes are the entire contract with news-agent-infra's
            # scheduler (infra-boundary-contract.md): 0 = updated, 2 = pricing
            # source unavailable this run (existing rates stay in effect, not
            # a failure), 1 = a real failure (e.g. the DB write itself).
            try:
                result = pricing_service.refresh_from_openrouter(db)
            except httpx.HTTPError:
                logging.getLogger(__name__).warning(
                    "refresh-pricing: pricing source unavailable, existing rates stay in effect",
                    exc_info=True,
                )
                return 2
            except Exception:
                logging.getLogger(__name__).error("refresh-pricing failed", exc_info=True)
                return 1
            print(f"Updated pricing for {result.updated} model(s)")
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
            sender = get_email_sender()
            send_report = send.send_pending_digests(db, sender)
            # Readers whose topics produced nothing still get their one-time
            # welcome, so finishing setup is never met with silence.
            welcome_report = send.send_pending_welcomes(db, sender)
            print(f"Sent {send_report.sent}, failed {send_report.failed}")
            print(
                f"Welcome-only: sent {welcome_report.sent}, failed {welcome_report.failed}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
