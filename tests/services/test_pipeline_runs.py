import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsagent.models import PipelineRun
from newsagent.models.base import Base
from newsagent.services.pipeline_runs import record_run


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_record_run_persists_all_given_fields(db: Session):
    record_run(
        db,
        run_type="filter",
        succeeded=7,
        refused=1,
        errors=2,
        usage_input_units=100,
        usage_output_units=50,
    )

    run = db.scalar(select(PipelineRun))
    assert run is not None
    assert run.run_type == "filter"
    assert run.succeeded == 7
    assert run.refused == 1
    assert run.errors == 2
    assert run.usage_input_units == 100
    assert run.usage_output_units == 50


def test_record_run_writes_a_row_for_a_zero_article_run(db: Session):
    record_run(
        db,
        run_type="summarize",
        succeeded=0,
        refused=0,
        errors=0,
        usage_input_units=0,
        usage_output_units=0,
    )

    run = db.scalar(select(PipelineRun))
    assert run is not None
    assert run.run_type == "summarize"
    assert run.succeeded == 0
    assert run.refused == 0
    assert run.errors == 0
    assert run.usage_input_units == 0
    assert run.usage_output_units == 0
