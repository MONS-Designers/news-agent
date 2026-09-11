# API Contracts - backend

**Date:** 2026-09-10
**Part:** `backend` (`src/newsagent`)
**Framework:** FastAPI 0.139.2
**App factory:** `create_app()` in `src/newsagent/api/main.py`

## Conventions

- All request and response bodies are JSON, serialized by Pydantic v2 models in
  `src/newsagent/api/schemas/`. Response models set `ConfigDict(from_attributes=True)`, so
  ORM objects and service dataclasses are returned straight from handlers.
- Authentication is a **signed session cookie**, not a bearer token. Starlette's
  `SessionMiddleware` signs the cookie with `NEWSAGENT_SESSION_SECRET`; the payload under
  key `identity` holds `email`, `is_admin` and `user_id`.
- Three guard dependencies live in `src/newsagent/api/auth.py`:
  - `require_identity` - 401 when there is no session.
  - `require_admin` - 401 without a session, 403 when `is_admin` is false.
  - `require_user` - 401 without a session, 403 when the session carries no `user_id` or
    the row is gone. Returns the `User` ORM object.
- CORS allows exactly one origin, `NEWSAGENT_FRONTEND_URL`, with credentials enabled. This
  matters only for split-subdomain deploys; the containerized frontend proxies `/api/`
  server-side, so the browser sees a same-origin request.
- Error bodies use FastAPI's default shape, `{"detail": "..."}`.

## Health

| Method | Path | Auth | Response |
| --- | --- | --- | --- |
| GET | `/health` | none | `{"status": "ok", "commit": "<GIT_SHA or unknown>"}` |
| GET | `/health/db` | none | `{"status": "ok"}`, or 503 with `{"status": "error"}` when `SELECT 1` fails |

`GIT_SHA` is baked into the image at build time, so a deploy can be verified against what
is actually running rather than against static App Service configuration.

## Auth - `/auth` (`routers/auth.py`)

| Method | Path | Auth | Behavior |
| --- | --- | --- | --- |
| GET | `/auth/login` | none | 302 to Google's consent screen. 503 when `NEWSAGENT_GOOGLE_CLIENT_ID` is empty. |
| GET | `/auth/callback` | none | OAuth callback. Resolves identity, writes the session, 302 into the SPA. |
| GET | `/auth/dev-login` | none | **Registered only when `NEWSAGENT_DEV_AUTH_EMAIL` is set.** Optional `?email=` overrides the target. |
| GET | `/auth/me` | session | `IdentityOut`, that is `email`, `is_admin`, `user_id` |
| POST | `/auth/logout` | none | Clears the session key, returns `{"status": "signed_out"}` |

### Redirect URI

`/auth/login` builds its `redirect_uri` as `{frontend_url}/api/auth/callback` and
deliberately does not use `request.url_for("callback")`. Behind a reverse proxy that
rewrites `Host` to the backend's own hostname, which Azure App Service routing requires,
`url_for` would resolve to the backend origin. That sends Google's redirect past the proxy
and sets the session cookie on the wrong origin.

### Callback outcomes

| Situation | Result |
| --- | --- |
| Google returns an `OAuthError`, or no `email` claim | 302 to `{frontend_url}/?error=oauth_failed` |
| Email matches an existing `User` | Session written, then 302 to `/admin` for an admin, `/` for a user with no profile yet, otherwise `/preferences` |
| Brand-new email, room under the cap | `User` row created, then the same redirect logic |
| Brand-new email, cap full, no `Admin` row | Email captured to `waitlist`, 302 to `{frontend_url}/?error=capacity_full` |
| Brand-new email, cap full, has an `Admin` row | Signs in with `user_id` null. An admin is never turned away. |

`given_name` and `family_name` from Google are stored only at row creation. An existing row
is never mutated, even when Google's claims later change. A non-string claim is dropped
rather than stored.

### Development login

`/auth/dev-login` is registered at import time inside an `if settings.dev_auth_email:`
block. When the setting is empty the route does not exist at all, rather than existing and
404-ing on a flag, so a stray value in a production environment cannot re-enable it. It
performs a real sign-in producing the same session the Google callback produces, so no code
on the authenticated request path ever skips a check. The API logs a warning on every boot
when the setting is populated.

## Admin - `/admin`, admin session required on every route

Three routers share the `/admin` prefix and declare `dependencies=[Depends(require_admin)]`
at router level, so the guard cannot be forgotten on an individual route.

### Sources (`routers/admin.py`)

| Method | Path | Body | Response |
| --- | --- | --- | --- |
| GET | `/admin/sources` | none | `list[SourceOut]`, pending sources only |
| PATCH | `/admin/sources/{source_id}` | `SourceStatusUpdate` | `SourceOut` |

`SourceOut` carries `id`, `topic_id`, `url`, `name`, `status`. `SourceStatusUpdate` carries
a single `status` field constrained to `approved` or `rejected`.

### Taxonomy queue (`routers/admin_taxonomy.py`)

| Method | Path | Body | Response |
| --- | --- | --- | --- |
| GET | `/admin/taxonomy` | none | `list[PendingTaxonomySuggestionOut]` |
| PATCH | `/admin/taxonomy/{suggestion_id}` | `TaxonomySuggestionDecision` | `PendingTaxonomySuggestionOut` |

`PendingTaxonomySuggestionOut` carries `id`, `kind`, `field_name`, `text`,
`submission_count`. `TaxonomySuggestionDecision` carries `status`, constrained to `approved`
or `rejected`, plus an optional `name`.

The optional `name` overrides the curated Field or Role name written on approval. Rows that
predate the `raw_text` column carry only casefolded text, so the admin corrects spelling
before the value becomes a user-visible option.

### Engagement (`routers/admin_engagement.py`)

| Method | Path | Response |
| --- | --- | --- |
| GET | `/admin/engagement` | `list[DigestEngagementOut]` |

`DigestEngagementOut` carries `digest_id`, `user_email`, `date`, `sent_at`, `opened_at`,
`articles_total`, `articles_clicked`, `clicked_article_titles`, `preferences_clicked`.

## Reader - `/me` (`routers/me.py`), `require_user` on every route

| Method | Path | Body | Response |
| --- | --- | --- | --- |
| GET | `/me/preferences` | none | `list[TopicPreferenceOut]` |
| PUT | `/me/preferences` | `PreferenceUpdateIn` | `list[TopicPreferenceOut]` |
| GET | `/me/subscription` | none | `SubscriptionOut` |
| PUT | `/me/subscription` | `SubscriptionUpdateIn` | `SubscriptionOut` |
| POST | `/me/feedback` | `FeedbackIn` | `{"status": "recorded"}` |
| GET | `/me/fields` | none | `list[FieldOut]` |
| GET | `/me/fields/{field_id}/roles` | none | `list[RoleOut]` |
| GET | `/me/profile` | none | `ProfileOut` |
| PUT | `/me/profile` | `ProfileUpdateIn` | `ProfileOut` |
| GET | `/me/topic-suggestions` | none | `TopicSuggestionsOut` |
| GET | `/me/prompt-suggestions` | none | `list[str]` |

### Schemas

```text
PreferenceUpdateIn   { topic_ids: int[], new_topic_names: str[] = [] }
TopicPreferenceOut   { topic_id: int, name: str, subscribed: bool }
SubscriptionOut      { unsubscribed: bool }
SubscriptionUpdateIn { unsubscribed: bool }
FeedbackIn           { rating: int|null, text: str|null }
FieldOut             { id: int, name: str }
RoleOut              { name: str, is_curated: bool }
ProfileUpdateIn      { field_name, field_is_other, role_name, role_is_other,
                       experience_bucket, interest_free_text }
ProfileOut           { field_name, role_name, experience_bucket,
                       interest_free_text, topics_stale_at }
TopicSuggestionsOut  { suggestion_status, suggested_topic_ids,
                       suggested_new_topic_names }
```

`RoleOut` carries no `id`. An uncurated, LLM-suggested role has no real `Role` row, so the
schema omits the field entirely rather than serving a fake or optional one.

`ProfileOut.topics_stale_at` is a nullable timestamp that the frontend treats as a boolean.
It is set when a profile edit diverges from the saved topics and cleared when the reader
next saves their topics. The subscriptions themselves are never touched.

### Validation behavior

- `PUT /me/preferences` returns 400 on `TopicCapExceededError` and on any other `ValueError`
  raised by `services.preferences.set_preferences`.
- `POST /me/feedback` returns 400 when `rating` falls outside 1 to 5, and 400 when neither a
  rating nor non-blank text is supplied. Over-long text is truncated by the service rather
  than rejected.
- `GET /me/fields/{field_id}/roles` returns 404 for an unknown field.
- `PUT /me/profile` returns 400 on any `ValueError` from `services.profile.save_profile`.

### Asynchronous suggestion computation

`PUT /me/profile` schedules a FastAPI `BackgroundTask` that recomputes topic suggestions. It
receives `db.get_bind()`, the engine, rather than the session, because the request-scoped
session is already closed by the time the task runs.

Progress is polled through `GET /me/topic-suggestions`, whose `suggestion_status` is one of
`none`, `pending`, `pending_slow`, `ready`, `failed`. The value `pending_slow` is
**non-terminal**: one of two concurrent calls has already failed and the survivor's retries
are still running. Clients must keep polling through it. Every run that writes it still
settles on `ready` or `failed`.

Suggestion state is deliberately kept out of `ProfileOut`. The suggestions endpoint is the
only read path for it.

## Tracking - public and unauthenticated (`routers/tracking.py`)

| Method | Path | Response |
| --- | --- | --- |
| GET | `/t/{token}.gif` | A 1x1 transparent GIF, always |
| GET | `/c/{token}` | 302 to the link's `target_url`, or a standalone HTML thank-you page for feedback and unsubscribe link kinds |

The token itself is the credential: unguessable, and unique per digest and per link. The
open pixel returns the same image whether or not the token is valid, so it cannot be used to
enumerate which tokens exist. The click redirect cannot offer that same guarantee because it
must know a real destination, but the token stays unguessable.

Both endpoints classify the requesting device from the `User-Agent` header through
`services.device_detection.classify_device`, storing one of `mobile`, `tablet`, `desktop`,
`bot`, `unknown` alongside the first open or click.

The feedback thank-you page is standalone right-to-left HTML rather than a redirect into the
single-page app. The earlier redirect mounted its confirmation toast only when a session was
active, so a signed-out click was recorded but looked to the reader like nothing happened.

## Interactive documentation

FastAPI serves the generated OpenAPI document at `/openapi.json` and Swagger UI at `/docs`.
No OpenAPI file is checked in; the schema is derived from route signatures at runtime.

---

_Generated using BMAD Method `document-project` workflow_
