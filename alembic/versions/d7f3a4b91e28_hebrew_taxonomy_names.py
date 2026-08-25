"""Rename curated Field/Role/Topic names from English to Hebrew

Revision ID: d7f3a4b91e28
Revises: c4e9a72f18db
Create Date: 2026-08-23

The names are user-facing labels rendered straight into the profile picker and
the digest, so Hebrew is the name itself - not a display shim over an English
key. `users.field_name`/`role_name` are denormalized string copies (AD-6: a
curated pick and a typed "Other" are stored identically), so they are renamed
alongside the taxonomy rows or existing profiles would point at names that no
longer exist.

Every rename is guarded by a NOT EXISTS on the target name: a promoted "Other"
suggestion may already have minted the Hebrew name, and the unique constraints
(fields.name, topics.name, uq_roles_field_name) would otherwise abort the whole
migration.
"""

import sqlalchemy as sa

from alembic import op

revision = "d7f3a4b91e28"
down_revision = "c4e9a72f18db"
branch_labels = None
depends_on = None


FIELDS = {
    "Tech": "טכנולוגיה",
    "Finance": "פיננסים",
    "Healthcare": "בריאות ורפואה",
    "Education": "חינוך",
    "Design": "עיצוב",
}

# (english_field, english_role, hebrew_role) - roles are unique per field, so
# "Researcher" under three different fields is three separate renames.
ROLES = [
    ("Tech", "Software Engineer", "מהנדס/ת תוכנה"),
    ("Tech", "Product Manager", "מנהל/ת מוצר"),
    ("Tech", "Data Scientist", "מדען/ית נתונים"),
    ("Tech", "Founder / Exec", "יזם/ית או מנהל/ת בכיר/ה"),
    ("Finance", "Analyst", "אנליסט/ית"),
    ("Finance", "Portfolio Manager", "מנהל/ת תיקי השקעות"),
    ("Finance", "Accountant", "רואה/ת חשבון"),
    ("Finance", "Founder / Exec", "יזם/ית או מנהל/ת בכיר/ה"),
    ("Healthcare", "Physician", "רופא/ה"),
    ("Healthcare", "Nurse", "אח/ות"),
    ("Healthcare", "Researcher", "חוקר/ת"),
    ("Healthcare", "Administrator", "מנהל/ת"),
    ("Education", "Teacher", "מורה"),
    ("Education", "Researcher", "חוקר/ת"),
    ("Education", "Administrator", "מנהל/ת"),
    ("Education", "Student", "סטודנט/ית"),
    ("Design", "Product Designer", "מעצב/ת מוצר"),
    ("Design", "Researcher", "חוקר/ת"),
    ("Design", "Art Director", "מנהל/ת אמנותי/ת"),
    ("Design", "Student", "סטודנט/ית"),
]

TOPICS = {
    "AI": "בינה מלאכותית",
    "Cybersecurity": "סייבר",
    "Space": "חלל",
}


def _rename_unique(table: str, old: str, new: str) -> None:
    op.execute(
        sa.text(
            f"UPDATE {table} SET name = :new WHERE name = :old "  # noqa: S608 - table is a literal
            f"AND NOT EXISTS (SELECT 1 FROM {table} t2 WHERE t2.name = :new)"
        ).bindparams(old=old, new=new)
    )


def _rename_role(field_name: str, old: str, new: str) -> None:
    op.execute(
        sa.text(
            "UPDATE roles SET name = :new WHERE name = :old "
            "AND field_id = (SELECT id FROM fields WHERE name = :field) "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM roles r2 WHERE r2.name = :new AND r2.field_id = roles.field_id"
            ")"
        ).bindparams(old=old, new=new, field=field_name)
    )


def _rename_user_column(column: str, old: str, new: str) -> None:
    op.execute(
        sa.text(
            f"UPDATE users SET {column} = :new WHERE {column} = :old"  # noqa: S608 - literal
        ).bindparams(old=old, new=new)
    )


def _apply(fields: dict[str, str], roles: list[tuple[str, str, str]], topics: dict[str, str]) -> None:
    # Roles first: _rename_role locates the field by its *current* name, so
    # renaming fields ahead of it would leave every role lookup unmatched.
    for english_field, old_role, new_role in roles:
        _rename_role(english_field, old_role, new_role)
        _rename_user_column("role_name", old_role, new_role)
    for old, new in fields.items():
        _rename_unique("fields", old, new)
        _rename_user_column("field_name", old, new)
    for old, new in topics.items():
        _rename_unique("topics", old, new)


def upgrade() -> None:
    _apply(FIELDS, ROLES, TOPICS)


def downgrade() -> None:
    _apply(
        {hebrew: english for english, hebrew in FIELDS.items()},
        [(FIELDS[f], hebrew, english) for f, english, hebrew in ROLES],
        {hebrew: english for english, hebrew in TOPICS.items()},
    )
