# V1 manual test plan

Written to be run by hand against a local environment, in order. Roughly 30–40 minutes
for the full pass. Automated tests cover the logic; this covers what only a person can
judge — whether the Hebrew reads well, whether the email looks right in a real inbox, and
whether the flow feels like two minutes.

Each check states **what to do**, **what should happen**, and **why it matters**, so a
failure tells you something rather than just going red.

---

## 0. One-time setup

The `.venv` is currently missing three packages that `requirements.txt` already lists
(`user-agents` and its two dependencies), which is why the API fails to start from it.
Fix first:

```bash
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

Then add to `.env`:

```
NEWSAGENT_DEV_AUTH_EMAIL=dev@example.com
NEWSAGENT_EMAIL_SENDER=console
NEWSAGENT_EMAIL_OUTBOX_DIR=./outbox
```

`console` + an outbox directory means every email is written to disk as HTML instead of
being sent — you can open each one in a browser and look at it.

Seed a database:

```bash
python -m alembic upgrade head
python -m newsagent.cli add-user dev@example.com --name "נעם מגנוס"
python -m newsagent.cli seed-fields
python -m newsagent.cli seed-roles
python -m newsagent.cli seed-sources
```

Start both processes (two terminals):

```bash
.venv/Scripts/uvicorn.exe newsagent.api.main:app --host 127.0.0.1 --port 8000 --reload
```

```bash
cd frontend && npm run dev
```

---

## 1. Signing in without Google

| | |
|---|---|
| **Do** | Open `http://127.0.0.1:8000/auth/dev-login` |
| **Expect** | Redirect into the app, header shows `dev@example.com` and a התנתקות button |
| **Why** | This is the whole dev-login mechanism. If it fails, nothing below can run |

**Also check:** the API log line on startup should warn that dev login is enabled. It is
supposed to be impossible to leave on without noticing.

**Switch accounts:** `http://127.0.0.1:8000/auth/dev-login?email=someone@example.com`
(the address must already exist, or be creatable under the user cap).

**Negative check — do this one:** remove `NEWSAGENT_DEV_AUTH_EMAIL` from `.env`, restart
the API, and visit `/auth/dev-login` again. It must return **404**, not a disabled page.
The route is only registered when the variable is set. Put the variable back afterwards.

---

## 2. Logo returns home

| | |
|---|---|
| **Do** | From `/preferences`, click the NewsAgent logo in the header |
| **Expect** | Lands on `/` |
| **Why** | It looked clickable and did nothing — the most common thing a first-time visitor tries |

---

## 3. Everything is in Hebrew

| | |
|---|---|
| **Do** | Go to `/preferences`. Look at the Field row. Pick טכנולוגיה and wait for the roles |
| **Expect** | Fields: טכנולוגיה, פיננסים, בריאות ורפואה, חינוך, עיצוב. Roles all Hebrew |
| **Why** | Two separate bugs — English in the database, and an LLM never told which language to answer in |

**The important part:** the role list mixes curated entries with LLM-generated ones. The
generated ones are the real test of the prompt fix. Terms like DevOps or UX/UI staying in
Latin script is intended, not a miss.

**Repeat for another field** (בריאות ורפואה) — the roles are generated per field, so one
passing does not prove the rest.

---

## 4. The profile flow, timed

| | |
|---|---|
| **Do** | Start a stopwatch. Complete all three steps as a genuinely new reader would |
| **Expect** | Under two minutes without rushing |
| **Why** | "Two minutes" is a promise made in the copy. If it takes four, the copy is wrong |

**Watch for on step 3 (topics):**

- Suggested topics appear as chips.
- **Only real topics are pre-selected.** Any LLM-invented name must be present but
  **unselected**. This is the fix for the reader who was auto-subscribed to two topics
  about autism they never chose — an invented topic has no RSS sources and would produce
  zero articles.
- Selecting a fifth topic should refuse and explain, not silently swap one out.

---

## 5. Feedback — all three entry points

### 5a. In the app

| | |
|---|---|
| **Do** | Click יש לך מה להגיד? bottom-left. Pick 👍, type a line, send |
| **Expect** | Panel closes, confirmation appears |
| **Why** | Must never fail and must not demand a form |

Also try: **thumb only, no text** — should send. **Text only, no thumb** — should send.
**Neither** — the send button stays disabled.

Confirm it was stored, not just rendered:

```bash
python -c "import sqlite3;c=sqlite3.connect('newsagent.db');[print(r) for r in c.execute('SELECT id,user_id,source,sentiment,text FROM feedback')]"
```

### 5b. and 5c. From the email

Covered in section 7 below, once there is an email to click in.

---

## 6. Responsive

| | |
|---|---|
| **Do** | DevTools device toolbar. Check the home page and the picker at 390px and 768px |
| **Expect** | No horizontal scrolling; chips wrap; the feedback button does not cover the primary action |
| **Why** | Most people will open this on a phone |

---

## 7. The first email

This is the centrepiece — it must land right.

```bash
python -m newsagent.cli fetch
python -m newsagent.cli filter
python -m newsagent.cli summarize
python -m newsagent.cli send-digests
```

Open the newest file in `./outbox` in a browser.

**Check, in order:**

1. **Subject line** — printed by the console sender. The first email should read
   `נעם, הדייג'סט הראשון שלך מוכן.` Later ones read `NewsAgent · <top headline>`.
   A date-only subject is a regression.
2. **Welcome block at the top** — present, warm, and **never mentions how many beta users
   there are**. Disclosing the cap invites "why can't my friend join?" and breaks when the
   cap changes.
3. **No gendered address.** Every line should work for a woman reading it. This is the one
   to read out loud.
4. **Body is flowing paragraphs, not bullets.** Articles summarised before this change keep
   the old shape until re-summarised — expected, not a bug.
5. **Logo links to the site.**
6. **👍/👎 beside each article** and a feedback block at the bottom.
7. Click a 👍 — it should record feedback and land on a thank-you. Check the `feedback`
   table again; `source` should read `article`.
8. Click the footer 👍 — same, but `source` reads `digest`.
9. Click רוצה להגיד משהו במילים — should open the app with the feedback panel already open.

**Then send again:**

```bash
python -m newsagent.cli send-digests
```

Nothing new should be sent, and no second welcome. `welcomed_at` and `sent_at` are what
make repeat runs safe.

---

## 8. The email when there are no articles

The case that would otherwise be **silence** right after someone finishes setup.

| | |
|---|---|
| **Do** | Add a reader whose topics have no articles: `python -m newsagent.cli add-user quiet@example.com --name "דנה"`, sign in as them via dev-login, complete the profile picking only an invented topic, then run `send-digests` |
| **Expect** | They receive a welcome-only email |
| **Why** | No `Digest` row exists for them, so the normal send path can never reach them |

**Check:** it has **no 👍/👎** (nothing to rate yet), the copy says the first digest is
still coming, and the feedback prompt asks what they want covered rather than how it was.

---

## 9. Editing a profile

| | |
|---|---|
| **Do** | As a reader with saved topics, go to `/preferences`, click עריכת פרופיל, change the Field, save step 1, then **leave without finishing step 3** |
| **Expect** | Returning to `/preferences` shows an amber banner saying the topics no longer match the profile, with a button to update them |
| **Why** | Previously the profile changed and the topics silently did not — they kept receiving the old field's articles |

**Then finish step 3 and save.** The banner must disappear. **Also check** that saving the
same profile unchanged does *not* raise the banner — it tracks real divergence, not the act
of pressing save.

**Deliberate non-behaviour:** the subscriptions are never auto-cleared. Quietly muting a
beta reader is worse than leaving them stale.

---

## 10. The scheduler

```bash
python -m newsagent.scheduler
```

| | |
|---|---|
| **Do** | Leave it running. Sign up a new reader via dev-login and complete the picker |
| **Expect** | Within about 2 minutes, their first email appears in `./outbox` with no CLI command typed |
| **Why** | This is the "strike while the iron is hot" promise — the whole point of the loop |

**Then:**

- **Leave it running another 5 minutes.** No further emails. Idle ticks must be no-ops.
- **Start a second scheduler in another terminal.** It must deliver nothing — the lease
  lets only one instance work. This is what makes extra replicas harmless.
- **Ctrl+C the first one.** It should finish its current tick and log that it stopped. The
  second should pick up within a couple of minutes.

Logs go to the `log_entries` table, not stdout — that is the project's design, not a fault:

```bash
python -c "import sqlite3;c=sqlite3.connect('newsagent.db');[print(r) for r in c.execute('SELECT level,logger_name,message FROM log_entries ORDER BY id DESC LIMIT 20')]"
```

---

## 11. Cost — no double payment

| | |
|---|---|
| **Do** | With `NEWSAGENT_LLM_PROVIDER=external`, note token usage: `python -m newsagent.cli usage-report`. Add a new reader on topics that already have summarised articles. Run the scheduler. Check usage again |
| **Expect** | No summarisation cost. Ideally no voice-composition cost either |
| **Why** | Article text is stored on the shared `Article` row, and a recent identical article set reuses its editorial voice |

If the voice **is** recomposed, the new reader's article set differed from the recent one —
worth understanding, not necessarily wrong.

---

## What this plan does not cover

- **Real Google OAuth.** Dev-login deliberately bypasses it. Sign-in against the real
  provider needs testing separately, on staging.
- **Real SMTP delivery.** `console` writes HTML to disk. How the email renders in actual
  Gmail and Outlook — especially the RTL layout and the handwriting font in the קינוח
  block — can only be judged by sending real mail to a real inbox.
- **The duplicate-send window.** A digest can be delivered twice if the process is killed
  between the SMTP handoff and the `sent_at` commit. Known, documented in
  `_bmad-output/implementation-artifacts/deferred-work.md`, deliberately not fixed.
