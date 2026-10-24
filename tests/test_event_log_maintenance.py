from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import event, inspect, text
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from database import ensure_event_log_indexes
from models import EventLog
from task_clean_logs import clean_old_logs


ROOT = Path(__file__).resolve().parents[1]


def make_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_existing_event_log_table_receives_query_indexes():
    engine = make_engine()
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE event_logs (
                    id INTEGER PRIMARY KEY,
                    app_id VARCHAR(64),
                    event_type VARCHAR(255) NOT NULL,
                    device_uuid VARCHAR(255),
                    status INTEGER DEFAULT 1,
                    created_at DATETIME NOT NULL
                )
                """
            )
        )

    ensure_event_log_indexes(engine)

    indexes = {item["name"]: item["column_names"] for item in inspect(engine).get_indexes("event_logs")}
    assert indexes["idx_event_logs_app_created"] == ["app_id", "created_at"]
    assert indexes["idx_event_logs_event_created"] == ["event_type", "created_at"]
    assert indexes["idx_event_logs_status_created"] == ["status", "created_at"]
    assert indexes["idx_event_logs_app_device_created"] == ["app_id", "device_uuid", "created_at"]
    assert indexes["idx_event_logs_device_created"] == ["device_uuid", "created_at"]


def test_old_event_logs_are_deleted_in_bounded_batches():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)
    now = datetime(2026, 10, 22, 12, 0, 0)

    with Session(engine) as session:
        for index in range(8):
            session.add(
                EventLog(
                    event_type="verify",
                    status=1,
                    created_at=now - timedelta(days=45, seconds=index),
                )
            )
        for index in range(2):
            session.add(
                EventLog(
                    event_type="verify",
                    status=1,
                    created_at=now - timedelta(days=index),
                )
            )
        session.commit()

    delete_batch_sizes: list[int] = []

    @event.listens_for(engine, "before_cursor_execute")
    def capture_delete(_conn, _cursor, statement, parameters, _context, _executemany):
        if statement.lstrip().lower().startswith("delete from event_logs"):
            delete_batch_sizes.append(len(parameters))

    deleted = clean_old_logs(
        retention_days=30,
        batch_size=3,
        target_engine=engine,
        now=now,
    )

    with Session(engine) as session:
        remaining = session.exec(select(EventLog)).all()

    assert deleted == 8
    assert len(remaining) == 2
    assert delete_batch_sizes == [3, 3, 2]


def test_event_log_cleanup_is_wired_into_the_application_lifecycle():
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")
    config_source = (ROOT / "config.py").read_text(encoding="utf-8")
    compose_source = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")

    assert "run_event_log_cleanup_loop" in main_source
    assert "app.state.event_log_cleanup_task = asyncio.create_task" in main_source
    assert '@app.on_event("shutdown")' in main_source
    assert "EVENT_LOG_RETENTION_DAYS: int = 30" in config_source
    assert "EVENT_LOG_CLEANUP_BATCH_SIZE: int = 1000" in config_source
    assert "EVENT_LOG_RETENTION_DAYS: ${EVENT_LOG_RETENTION_DAYS:-30}" in compose_source
