"""
日志清理定时任务 - 每30天自动清理过期日志
"""
import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlmodel import Session, delete, select

from database import engine
from models import EventLog, get_now


_CLEANUP_LOCK_NAME = "lemon_kami:event_log_cleanup"


def clean_old_logs(
    retention_days: int = 30,
    *,
    batch_size: int = 1000,
    target_engine=None,
    now: datetime | None = None,
) -> int:
    """Delete expired event logs in bounded batches and return the deleted count."""
    if retention_days < 1:
        raise ValueError("retention_days must be positive")
    if batch_size < 1:
        raise ValueError("batch_size must be positive")

    selected_engine = target_engine or engine
    current_time = now or get_now().replace(tzinfo=None)
    cutoff_date = current_time - timedelta(days=retention_days)
    deleted_count = 0
    lock_connection = None

    if selected_engine.dialect.name == "mysql":
        lock_connection = selected_engine.connect()
        lock_acquired = lock_connection.execute(
            text("SELECT GET_LOCK(:lock_name, 0)"),
            {"lock_name": _CLEANUP_LOCK_NAME},
        ).scalar()
        if lock_acquired != 1:
            lock_connection.close()
            return 0

    try:
        while True:
            with Session(selected_engine) as session:
                old_ids = session.exec(
                    select(EventLog.id)
                    .where(EventLog.created_at < cutoff_date)
                    .order_by(EventLog.id)
                    .limit(batch_size)
                ).all()
                if not old_ids:
                    break
                session.exec(delete(EventLog).where(EventLog.id.in_(old_ids)))
                session.commit()
                deleted_count += len(old_ids)
    finally:
        if lock_connection is not None:
            try:
                lock_connection.execute(
                    text("SELECT RELEASE_LOCK(:lock_name)"),
                    {"lock_name": _CLEANUP_LOCK_NAME},
                )
            finally:
                lock_connection.close()

    return deleted_count


async def run_event_log_cleanup_loop(
    *,
    retention_days: int = 30,
    batch_size: int = 1000,
    interval_seconds: int = 86400,
    initial_delay_seconds: int = 60,
    logger: logging.Logger | None = None,
) -> None:
    """Run bounded event-log cleanup without blocking the API event loop."""
    await asyncio.sleep(max(0, initial_delay_seconds))
    while True:
        try:
            count = await asyncio.to_thread(
                clean_old_logs,
                retention_days,
                batch_size=batch_size,
            )
            if logger:
                logger.info("Event log cleanup deleted %s expired rows", count)
        except asyncio.CancelledError:
            raise
        except Exception:
            if logger:
                logger.exception("Event log cleanup failed")
        await asyncio.sleep(max(60, interval_seconds))


async def main():
    """主函数 - 定期执行清理"""
    print("🕒 启动日志清理定时任务...")
    print(f"📅 日志保留期：30天")
    print(f"⏰ 检查频率：每天凌晨2点\n")
    await run_event_log_cleanup_loop(initial_delay_seconds=0)


if __name__ == "__main__":
    asyncio.run(main())
