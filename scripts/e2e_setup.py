"""One-shot setup for the frontend Playwright E2E suite (frontend/e2e/).

Builds a fresh, throwaway sqlite DB (schema + fixture rows) and prints signed
session cookies for a handful of fixture identities, so E2E tests can skip
real Google OAuth entirely - Starlette's SessionMiddleware only ever checks
the signature, not how the cookie was produced.

Must be run as a subprocess with the same NEWSAGENT_DATABASE_URL and
NEWSAGENT_SESSION_SECRET the E2E backend process uses (see
frontend/playwright.config.ts) - both are throwaway, test-only values, never
the real .env/Neon DB or the real session secret.
"""

import base64
import json
import os
import sys

import itsdangerous
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from newsagent.config import settings
from newsagent.models import Admin, Topic, User
from newsagent.models.base import Base
from newsagent.services import taxonomy


def mint_cookie(identity: dict) -> str:
    payload = base64.b64encode(json.dumps({"identity": identity}).encode("utf-8"))
    signer = itsdangerous.TimestampSigner(str(settings.session_secret))
    return signer.sign(payload).decode("utf-8")


def main() -> None:
    db_path = settings.database_url.removeprefix("sqlite:///")
    if db_path and os.path.exists(db_path):
        os.remove(db_path)

    engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        taxonomy.seed_default_fields(db)
        taxonomy.seed_default_roles(db)
        db.add_all([Topic(name="AI"), Topic(name="Cybersecurity"), Topic(name="Space")])

        admin = Admin(email="e2e-admin@example.com")
        new_user = User(email="e2e-new-user@example.com", name="E2E New User")
        profiled_user = User(
            email="e2e-profiled-user@example.com",
            name="E2E Profiled User",
            field_name="Tech",
            role_name="Software Engineer",
            experience_bucket="3-5",
        )
        db.add_all([admin, new_user, profiled_user])
        db.commit()

        # A couple of pending "Other" suggestions for the admin taxonomy flow.
        taxonomy.record_pending_suggestion(db, kind="field", field_id=None, text="Robotics")
        tech = next(f for f in taxonomy.list_fields(db) if f.name == "Tech")
        taxonomy.record_pending_suggestion(db, kind="role", field_id=tech.id, text="DevRel Engineer")
        db.commit()

        identities = {
            "admin": {"email": admin.email, "is_admin": True, "user_id": None},
            "new_user": {"email": new_user.email, "is_admin": False, "user_id": new_user.id},
            "profiled_user": {
                "email": profiled_user.email,
                "is_admin": False,
                "user_id": profiled_user.id,
            },
        }

    cookies = {name: mint_cookie(identity) for name, identity in identities.items()}
    json.dump(cookies, sys.stdout)


if __name__ == "__main__":
    main()
