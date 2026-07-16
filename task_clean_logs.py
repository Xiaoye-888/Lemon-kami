"""
日志清理定时任务 - 每30天自动清理过期日志
"""
import asyncio
from datetime import datetime, timedelta
from sqlmodel import Session, select, delete
from database import engine
from models import EventLog, get_now


async def clean_old_logs(retention_days: int = 30):
    """清理超过保留期的日志"""
    # get_now() 返回带时区的时间，需要去掉时区信息后与数据库中的 naive datetime 比较
    cutoff_date = get_now().replace(tzinfo=None) - timedelta(days=retention_days)
    
    with Session(engine) as session:
        # 查询需要删除的日志数量
        statement = select(EventLog).where(EventLog.created_at < cutoff_date)
        old_logs = session.exec(statement).all()
        
        if old_logs:
            count = len(old_logs)
            # 删除旧日志
            delete_statement = delete(EventLog).where(EventLog.created_at < cutoff_date)
            session.exec(delete_statement)
            session.commit()
            
            print(f"[{get_now().isoformat()}] ✅ 已清理 {count} 条过期日志（{retention_days}天前）")
        else:
            print(f"[{get_now().isoformat()}] ℹ️ 无需清理日志")


async def main():
    """主函数 - 定期执行清理"""
    print("🕒 启动日志清理定时任务...")
    print(f"📅 日志保留期：30天")
    print(f"⏰ 检查频率：每天凌晨2点\n")
    
    while True:
        try:
            await clean_old_logs(retention_days=30)
        except Exception as e:
            print(f"❌ 日志清理失败: {e}")
        
        # 等待到明天凌晨2点
        now = get_now()
        tomorrow = now + timedelta(days=1)
        next_run = tomorrow.replace(hour=2, minute=0, second=0, microsecond=0)
        wait_seconds = (next_run - now).total_seconds()
        
        print(f"⏳ 下次清理时间: {next_run.isoformat()} ({wait_seconds/3600:.1f}小时后)\n")
        await asyncio.sleep(wait_seconds)


if __name__ == "__main__":
    asyncio.run(main())
