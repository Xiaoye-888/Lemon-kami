from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from kami_query_service import batch_stats_payloads, kami_search_payload
from models import App, Kami, KamiBatch, KamiDeviceBinding, KamiStatus, KamiType


def make_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_kami_search_uses_database_count_and_page_limit():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            App(
                app_id="app_page_perf",
                name="Page performance",
                app_secret="secret",
                rsa_public_key="public",
                rsa_private_key="private",
            )
        )
        for index in range(35):
            session.add(
                Kami(
                    app_id="app_page_perf",
                    kami_code=f"PAGE-{index:03d}",
                    kami_type=KamiType.lifetime,
                )
            )
        session.commit()

    statements: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def capture_statement(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(" ".join(statement.lower().split()))

    with Session(engine) as session:
        payload = kami_search_payload(
            session,
            select(Kami).where(Kami.app_id == "app_page_perf"),
            page=2,
            page_size=7,
        )

    assert payload["total"] == 35
    assert len(payload["items"]) == 7
    assert payload["items"][0]["kami_code"] == "PAGE-027"

    kami_statements = [statement for statement in statements if "kamis" in statement]
    assert any("count(" in statement for statement in kami_statements)
    assert any(" limit " in statement and " offset " in statement for statement in kami_statements)


def test_batch_stats_are_aggregated_in_one_query_for_multiple_batches():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            App(
                app_id="app_batch_perf",
                name="Batch performance",
                app_secret="secret",
                rsa_public_key="public",
                rsa_private_key="private",
            )
        )
        batches = [
            KamiBatch(
                app_id="app_batch_perf",
                batch_no=f"BATCH-{index}",
                kami_type=KamiType.lifetime,
                created_by_user_id=11,
            )
            for index in range(4)
        ]
        session.add_all(batches)
        session.commit()
        for batch in batches:
            session.refresh(batch)
            for card_index in range(5):
                code = f"{batch.batch_no}-CARD-{card_index}"
                session.add(
                    Kami(
                        app_id=batch.app_id,
                        kami_code=code,
                        batch_no=batch.batch_no,
                        kami_type=KamiType.lifetime,
                        status=KamiStatus.active if card_index == 0 else KamiStatus.unused,
                        created_by_user_id=11,
                    )
                )
                if card_index == 0:
                    session.add(
                        KamiDeviceBinding(
                            app_id=batch.app_id,
                            kami_code=code,
                            device_uuid=f"device-{batch.id}",
                            fingerprint=f"fingerprint-{batch.id}",
                        )
                    )
        session.commit()

    statements: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def capture_batch_statement(_conn, _cursor, statement, _parameters, _context, _executemany):
        normalized = " ".join(statement.lower().split())
        if normalized.startswith("select") and "kamis" in normalized:
            statements.append(normalized)

    with Session(engine) as session:
        batches = session.exec(select(KamiBatch).order_by(KamiBatch.id)).all()
        statements.clear()
        stats_by_id = batch_stats_payloads(
            session,
            batches,
            created_by_user_id=11,
        )

    assert len(statements) == 1
    assert len(stats_by_id) == 4
    for batch in batches:
        assert stats_by_id[batch.id] == {
            "total_count": 5,
            "unused_count": 4,
            "active_count": 1,
            "frozen_count": 0,
            "expired_count": 0,
            "device_bound_count": 1,
        }
