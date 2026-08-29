"""Pure unit coverage of newsagent.telemetry.context - the ambient-identity
half of AD-11, independent of any DB write. See test_call_recording.py for
the end-to-end (measurer -> context -> writer) coverage of the spec's frozen
I/O & Edge-Case Matrix.
"""

from newsagent.telemetry import context
from newsagent.telemetry.types import PURPOSE_FILTERING, PURPOSE_UNATTRIBUTED


def test_no_open_context_reads_as_unattributed():
    attribution = context.current_attribution()
    assert attribution.purpose == PURPOSE_UNATTRIBUTED
    assert attribution.run_id is None
    assert attribution.article_id is None
    assert attribution.attempt == 1


def test_attribute_call_supplies_purpose_and_article_id():
    with context.attribute_call(PURPOSE_FILTERING, article_id=42):
        attribution = context.current_attribution()
    assert attribution.purpose == PURPOSE_FILTERING
    assert attribution.article_id == 42


def test_attribute_call_resets_on_exit():
    with context.attribute_call(PURPOSE_FILTERING, article_id=42):
        pass
    assert context.current_attribution().purpose == PURPOSE_UNATTRIBUTED


def test_increment_attempt_is_a_noop_outside_attribute_call():
    assert context.increment_attempt() == 1
    assert context.increment_attempt() == 1


def test_increment_attempt_counts_up_inside_attribute_call():
    with context.attribute_call(PURPOSE_FILTERING, article_id=1):
        assert context.increment_attempt() == 1
        assert context.increment_attempt() == 2
        assert context.current_attribution().attempt == 2


def test_attribute_call_without_open_run_has_no_run_id():
    with context.attribute_call(PURPOSE_FILTERING, article_id=1):
        assert context.current_attribution().run_id is None


def test_open_run_supplies_run_id_to_nested_attribute_call(monkeypatch):
    monkeypatch.setattr(context.sink, "create_run", lambda **_: 7)
    monkeypatch.setattr(context.sink, "finish_run", lambda *_a, **_k: None)

    with context.open_run("filter", subscriber_count=3):
        with context.attribute_call(PURPOSE_FILTERING, article_id=1):
            assert context.current_attribution().run_id == 7

    # Reset once the run closes.
    assert context.current_attribution().run_id is None


def test_open_run_survives_create_run_returning_none(monkeypatch):
    """create_run() itself swallows failures and returns None (AD-13's error
    rule) - open_run must not crash just because telemetry couldn't open a
    row for this run."""
    monkeypatch.setattr(context.sink, "create_run", lambda **_: None)
    finished: list[tuple] = []
    monkeypatch.setattr(
        context.sink, "finish_run", lambda run_id, **kw: finished.append((run_id, kw))
    )

    with context.open_run("filter") as run:
        assert run.run_id is None

    assert finished == [(None, {"succeeded": 0, "refused": 0, "errors": 0})]


def test_run_close_values_flow_into_finish_run(monkeypatch):
    finished: list[tuple] = []
    monkeypatch.setattr(context.sink, "create_run", lambda **_: 5)
    monkeypatch.setattr(
        context.sink, "finish_run", lambda run_id, **kw: finished.append((run_id, kw))
    )

    with context.open_run("filter") as run:
        run.close(succeeded=3, refused=1, errors=2)

    assert finished == [(5, {"succeeded": 3, "refused": 1, "errors": 2})]


def test_unclosed_run_still_finishes_with_zero_defaults(monkeypatch):
    """If the with-block exits (e.g. via an exception) before run.close() is
    reached, the run must still be finished rather than left open forever."""
    finished: list[tuple] = []
    monkeypatch.setattr(context.sink, "create_run", lambda **_: 9)
    monkeypatch.setattr(
        context.sink, "finish_run", lambda run_id, **kw: finished.append((run_id, kw))
    )

    with context.open_run("filter"):
        pass

    assert finished == [(9, {"succeeded": 0, "refused": 0, "errors": 0})]
