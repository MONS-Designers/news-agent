# User management

Who can sign in is controlled entirely by the database — Google OAuth only authenticates; it never
creates accounts. A Google account can access the app only if its email exists in the `admins`
table (grants `/admin`) and/or the `users` table (grants `/preferences`). Emails are normalized to
lowercase before storage and matching.

Adding people is done with the operator CLI from the project root (venv active, migrations
applied). This works without any signed-in admin, which is also how the very first admin is
bootstrapped.

## Add an admin

```bash
python -m newsagent.cli add-admin someone@example.com
```

Grants access to the admin panel (`/admin`) — source approval.

## Add a regular user

```bash
python -m newsagent.cli add-user someone@example.com --name "Full Name"
```

`--name` is optional. Grants access to the preferences page (`/preferences`) and includes the user
in digest delivery.

## Notes

- Both commands are idempotent — running them again with the same email prints
  `Already exists` and changes nothing, so they're safe to use in seed scripts.
- The same email can be both an admin and a user (add it with both commands).
- The email must be the exact Google account the person signs in with.
- If the CLI fails with `no such table`, run `alembic upgrade head` first.
