---
title: 'Swappable log destination (config-driven, not hardcoded to stderr)'
type: 'feature'
created: '2026-08-02'
status: 'done'
baseline_commit: '7fdcf270d61e0ff812e58617a3c1fbabbc6ea85d'
review_loop_iteration: 3
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Nothing in `src/newsagent` configures logging — every call site does `logger = logging.getLogger(__name__)` and relies on Python's last-resort handler (WARNING+ to stderr, unredirectable without editing code). GH #38's diagnosis needs raw LLM responses written somewhere persistent, which today means ad-hoc shell redirection on every run.

**Approach:** Add a `configure_logging()` entrypoint hook that installs a stdlib `logging.Handler` chosen by a new `NEWSAGENT_LOG_DESTINATION` setting, with `NEWSAGENT_LOG_LEVEL` and `NEWSAGENT_LOG_FILE` alongside it. Every runnable entrypoint calls it. No existing call site changes.

## Boundaries & Constraints

**Always:**
- Use stdlib handlers (`StreamHandler`, `FileHandler`) as the swappable abstraction — config selects a handler, there is no custom base class.
- Mirror `mail/factory.py`: read the `settings` singleton; raise `ValueError` naming the bad value *and* the known values.
- Default config keeps destination = stderr and level = WARNING, matching today's observable behavior.
- `configure_logging()` is safe to call twice — a second call replaces handlers, never accumulates.
- Existing `getLogger(__name__)` call sites stay untouched.
- The destination is an operator-facing capture of everything worth watching in a deployment: application records **and** the API server's own startup/error/access output. `uvicorn`, `uvicorn.error`, and `uvicorn.access` set `propagate=False` with their own handlers, so they must be explicitly re-pointed at the root logger.
- Noisy third-party loggers (`httpx`, `httpcore`) are pinned to WARNING so `LOG_LEVEL=DEBUG` surfaces application records rather than transport traces.
- Config values are normalized before use: surrounding whitespace stripped, destination and level case-insensitive, an empty destination treated as unset (stderr).
- A `file` destination creates its parent directory if missing; any other open failure raises `ValueError` naming `NEWSAGENT_LOG_FILE`.

**Ask First:**
- Any destination beyond `stderr` / `stdout` / `file` — notably the future "send to an external service" destinations (WhatsApp / SMS / email).
- Pinning any logger beyond the `httpx` / `httpcore` pair named above.

**Never:**
- Do not implement any part of GH #38. This spec only makes the destination configurable.
- No rotation, size caps, or retention — record as deferred work instead.
- Do not name the module `newsagent/logging.py`; it shadows the stdlib name for readers.
- Do not call `configure_logging()` from `newsagent/__init__.py` or any library module.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Default | No `NEWSAGENT_LOG_*` set | Exactly one root `StreamHandler` on `sys.stderr`; root level `WARNING` | N/A |
| Explicit stdout | `LOG_DESTINATION=stdout` | Single `StreamHandler` on `sys.stdout` | N/A |
| File | `LOG_DESTINATION=file`, `LOG_FILE=/tmp/na.log` | Single `FileHandler` (append, utf-8); an emitted WARNING appears in the file | N/A |
| File, no path | `LOG_DESTINATION=file`, `LOG_FILE` empty or whitespace | No handler installed | `ValueError` naming `NEWSAGENT_LOG_FILE` as required |
| File, missing dir | `LOG_FILE=./logs/na.log`, no `logs/` | Parent directory created, handler installed | N/A |
| File, unopenable | `LOG_FILE` is a directory / unwritable | No handler installed | `ValueError` naming `NEWSAGENT_LOG_FILE` and the OS reason |
| Unknown destination | `LOG_DESTINATION=kafka` | No handler installed | `ValueError` containing `kafka` + known destinations |
| Casing / padding | `LOG_DESTINATION=" STDERR "`, `LOG_LEVEL=" debug "` | Normalized and accepted | N/A |
| Empty destination | `LOG_DESTINATION=` (set but empty) | Treated as unset — stderr | N/A |
| Level override | `LOG_LEVEL=DEBUG` | Root level `DEBUG`; a pipeline `logger.debug(...)` reaches the destination | N/A |
| Numeric level | `LOG_LEVEL=20` | Root level `INFO` | N/A |
| Unknown level | `LOG_LEVEL=CHATTY` | No handler installed | `ValueError` containing `CHATTY` + known level names |
| NOTSET rejected | `LOG_LEVEL=NOTSET` or `LOG_LEVEL=0` | No handler installed | `ValueError` — level 0 would emit every third-party record |
| Level out of range | `LOG_LEVEL=999` | No handler installed | `ValueError` — a handler that can never emit is silent failure |
| Empty level | `LOG_LEVEL=` (set but empty) | Treated as unset — WARNING | N/A |
| Strict level wins | `LOG_LEVEL=ERROR`, API under uvicorn | Application ERROR reaches the destination; uvicorn INFO and `httpx` WARNING do not | N/A |
| Server logs captured | `LOG_DESTINATION=file`, API running under uvicorn | `uvicorn`, `uvicorn.error`, `uvicorn.access` records reach the same file | N/A |
| Third-party noise | `LOG_LEVEL=DEBUG` | `httpx` / `httpcore` stay at WARNING; application DEBUG still reaches the destination | N/A |
| Called twice | `configure_logging()` twice in one process | Root still has exactly one handler | N/A |

</frozen-after-approval>

## Code Map

- `src/newsagent/config.py` -- `Settings` (pydantic-settings, `NEWSAGENT_` prefix). Add the three settings beside `email_sender`/`email_outbox_dir`.
- `src/newsagent/logging_setup.py` -- NEW. `configure_logging()` + destination→handler mapping.
- `src/newsagent/cli.py:18` -- `main()`. First entrypoint.
- `src/newsagent/api/main.py:8` -- `create_app()`. Second entrypoint. `app = create_app()` runs at *module import*, so this fires during test collection too — the WARNING default keeps that inert.
- `src/newsagent/mail/factory.py` -- convention to copy (config read + `ValueError`).
- `tests/mail/test_factory.py` -- convention to copy (`monkeypatch.setattr(settings, ...)`).
- `src/newsagent/pipeline/{relevance,summarize,digest,fetcher,send}.py` -- the five existing call sites. Read-only; must work with zero edits.

## Tasks & Acceptance

**Execution:**
- [x] `src/newsagent/config.py` -- Add `log_destination: str = "stderr"`, `log_level: str = "WARNING"`, `log_file: str = ""` with a short comment pointing at `newsagent.logging_setup`, matching existing comment style.
- [x] `src/newsagent/logging_setup.py` -- Add `configure_logging() -> None`: resolve handler from `settings.log_destination`, validate the level, install via `logging.basicConfig(handlers=[handler], level=..., format=..., force=True)`.
- [x] `src/newsagent/cli.py` -- Call `configure_logging()` as the first statement in `main()`, before `parse_args`.
- [x] `src/newsagent/api/main.py` -- Call `configure_logging()` as the first statement in `create_app()`.
- [x] `tests/test_logging_setup.py` -- Cover every I/O Matrix row. Include an autouse fixture snapshotting and restoring `logging.root.handlers` and `logging.root.level` -- these tests mutate global state and will corrupt sibling suites otherwise.
- [x] `README.md` -- Document the three settings in the existing configuration/env section.
- [x] `_bmad-output/implementation-artifacts/deferred-work.md` -- Append one entry for log rotation / size caps.
- [x] `src/newsagent/logging_setup.py` -- Round 2: normalize/validate config values, auto-create the log dir, wrap open failures, capture the uvicorn loggers, pin `httpx`/`httpcore`.
- [x] `src/newsagent/llm/demo.py` -- Call `configure_logging()` in the `__main__` block -- it drives the external-LLM path GH #38 diagnoses.
- [x] `tests/test_logging_setup.py` -- Round 2: cover the new matrix rows; monkeypatch the default-asserting tests to code defaults so a local `.env` cannot break them; pin the timestamp format and append mode.
- [x] `README.md` -- Round 2: PowerShell-compatible env syntax, and note that server logs are captured too.
- [x] `_bmad-output/implementation-artifacts/deferred-work.md` -- Round 2: append entries for the Windows file lock, concurrent multi-process append, `force=True` vs `caplog`, and the future external-service destinations.

**Acceptance Criteria:**
- Given no `NEWSAGENT_LOG_*` variables, when the CLI or API starts, then WARNING+ records still go to stderr and nothing below WARNING is emitted.
- Given `LOG_DESTINATION=file` and a writable `LOG_FILE`, when `python -m newsagent.cli fetch` runs, then log output lands in that file, with no source file outside `config.py`, `logging_setup.py`, `cli.py`, `api/main.py`, `llm/demo.py` modified to achieve it.
- Given those same settings, when the API runs under uvicorn, then both `newsagent.*` records and uvicorn's own startup/error/access records reach that file.
- Given `LOG_LEVEL=DEBUG` and a file destination, when a pipeline module calls `logger.debug(...)`, then the record reaches the file while `httpx`/`httpcore` transport traces do not — the mechanism GH #38 will use.
- Given a misconfigured `LOG_FILE` (unwritable, or a directory), when any entrypoint starts, then it fails with a `ValueError` naming `NEWSAGENT_LOG_FILE` rather than a bare OS traceback.

## Spec Change Log

- **2026-08-06 — iteration 1, triggered by adversarial + edge-case review.**
  - *Finding (intent_gap):* AC3 said the API's "output goes to the same file", but `uvicorn`, `uvicorn.error`, and `uvicorn.access` set `propagate=False` with their own handlers, so swapping the root handler could never reach them. Two readings existed (application records only vs. everything the API process emits), so intent could not be inferred.
  - *Resolution by the user:* the destination is an operator-facing capture of **everything** relevant to whoever runs the deployment — server output, errors, INFO, and LLM-call tracking. The frozen Intent, Boundaries, and Matrix were renegotiated accordingly.
  - *Also amended (bad_spec):* the Matrix covered only `LOG_FILE` empty, never `LOG_FILE` set-but-unopenable — the far likelier operator mistake, which crashed the API at import with a raw `FileNotFoundError`. Added rows for missing dir (auto-create), unopenable path, casing/padding, empty destination, numeric level, and `NOTSET`.
  - *Known-bad state avoided:* shipping a "swappable log destination" where the server's own error and access logs silently bypass it, and where a one-character path typo takes down the API with an unattributed traceback.
- **2026-08-06 — iteration 3, triggered by round-2 edge-case review.**
  - *Findings (patch):* (a) `uvicorn --no-access-log` was silently re-enabled — its opt-out is `handlers=[] + propagate=False`, which the unconditional `propagate=True` overrode, resurrecting access lines whose tracking-pixel URLs embed user and article ids. (b) Server handlers were cleared but never closed, leaking an fd and, on Windows, locking the old file for the process lifetime. (c) Numeric levels 1-9 were accepted, sitting below DEBUG and thus emitting everything — the state the `0` check exists to block. (d) The `stdout` destination dropped records outright: reproduced `UnicodeEncodeError` for a Chinese/Russian source title on this project's `cp1255` console, since `sys.stdout` encodes strictly while `sys.stderr` defaults to `backslashreplace`.
  - *Amended:* honor the explicit access-log opt-out; close handlers on removal; numeric range tightened to `DEBUG`-`CRITICAL`; stream destinations reconfigured to `backslashreplace`.
  - *Known-bad state avoided:* a digest product whose whole purpose is ingesting articles in any source language, silently losing the log records for exactly the non-Hebrew, non-Latin articles most likely to be malformed.
  - *KEEP:* the encoding test asserts the handler's `errors` mode rather than captured output — `capsys` re-wraps streams and would mask the very defect under test.

- **2026-08-06 — iteration 2, triggered by round-2 adversarial review.**
  - *Finding (bad_spec):* `LOG_LEVEL` did not actually govern the loggers iteration 1 re-pointed. A record is filtered by the level of the logger that emitted it, not root's; uvicorn pins itself to INFO, and the `httpx`/`httpcore` pin *raised* their floor. Reproduced: at `LOG_LEVEL=ERROR` the application's own WARNING was suppressed while uvicorn INFO and httpx WARNING still reached the file — the inverse of operator intent, and a violation of AC1.
  - *Amended:* server loggers reset to `NOTSET` so they inherit the configured root level; noisy loggers use `max(level, WARNING)` so a stricter setting still wins. Matrix gained rows for strict-level-wins, numeric `0`, out-of-range levels, and empty level. Also: `isdecimal` over `isdigit`, `expanduser()` moved inside the error guard, and `*.log`/`logs/` added to `.gitignore` because the README's own DEBUG recipe writes raw LLM responses and article text into the repo.
  - *Known-bad state avoided:* an operator raising the level to quiet a noisy deployment gets a log file containing *only* the noise they were trying to remove.
  - *KEEP:* the level-governs-everything test that exercises a level other than the loggers' own defaults — round 2's original server test used `INFO`, the one level at which this bug was invisible.
  - *KEEP (from iteration 1):* the stdlib-handler-not-custom-interface decision; `basicConfig(force=True)` for idempotency; the timestamped format and its stated justification; `configure_logging()` called explicitly at entrypoints rather than on package import; the WARNING/stderr default that keeps pytest collection inert.

## Design Notes

**`force=True` rather than a `_configured` flag.** `basicConfig(force=True)` removes and closes existing root handlers before installing the new one, giving idempotency without hand-rolled state. Relevant because `api/main.py` configures at import while `cli.py` configures inside `main()`.

**Record format changes slightly, intentionally.** The last-resort handler emits a bare message; a file log without timestamps is not diagnosable. Use `"%(asctime)s %(levelname)s %(name)s: %(message)s"`. "Unchanged default behavior" above means *destination and level*, not byte-identical text.

## Verification

**Commands:**
- `python -m pytest tests/ -q` -- expected: all pass, including new `tests/test_logging_setup.py`, with no new failures in sibling suites (guards against leaked global logging state).
- `python -m ruff check src tests` -- expected: clean.
- `python -m mypy` -- expected: no new errors.
- `NEWSAGENT_LOG_DESTINATION=file NEWSAGENT_LOG_FILE=./tmp-na.log NEWSAGENT_LOG_LEVEL=DEBUG python -m newsagent.cli fetch` -- expected: `tmp-na.log` created, containing timestamped records from `newsagent.pipeline.fetcher`. Delete afterwards.

## Suggested Review Order

**Destination selection — the core mechanism**

- Entry point: one config value picks a stdlib handler, no custom interface.
  [`logging_setup.py:28`](../../src/newsagent/logging_setup.py#L28)

- File destination: creates the dir, and names the setting on any open failure.
  [`logging_setup.py:50`](../../src/newsagent/logging_setup.py#L50)

- Console destinations re-encode leniently — strict stdout silently drops foreign-language titles.
  [`logging_setup.py:31`](../../src/newsagent/logging_setup.py#L31)

**Level resolution — where the sharpest bugs were**

- Rejects NOTSET, numeric 0, and sub-DEBUG values that would emit everything.
  [`logging_setup.py:67`](../../src/newsagent/logging_setup.py#L67)

**Capturing the whole deployment, not just newsagent records**

- uvicorn sets propagate=False; re-pointing it is what makes server logs land.
  [`logging_setup.py:106`](../../src/newsagent/logging_setup.py#L106)

- NOTSET reset: a record is filtered by its own logger's level, never root's.
  [`logging_setup.py:122`](../../src/newsagent/logging_setup.py#L122)

- Honors `--no-access-log`; those lines carry tracking-pixel user and article ids.
  [`logging_setup.py:112`](../../src/newsagent/logging_setup.py#L112)

**Wiring — three entrypoints, unchanged call sites**

- Three new settings, defaults reproducing today's behavior exactly.
  [`config.py:39`](../../src/newsagent/config.py#L39)

- CLI entrypoint, before argument parsing.
  [`cli.py:19`](../../src/newsagent/cli.py#L19)

- API entrypoint; runs at import, which is how uvicorn picks it up.
  [`main.py:9`](../../src/newsagent/api/main.py#L9)

- Demo script — drives the external-LLM path GH #38 diagnoses.
  [`demo.py:47`](../../src/newsagent/llm/demo.py#L47)

**Supporting**

- 31 tests; the fixture restores all six loggers `configure_logging` mutates.
  [`test_logging_setup.py:24`](../../tests/test_logging_setup.py#L24)

- Operator docs, PowerShell-first, plus the level-precedence rule.
  [`README.md:42`](../../README.md#L42)

- DEBUG logs hold raw LLM responses and article text — keep them out of git.
  [`.gitignore:7`](../../.gitignore#L7)
