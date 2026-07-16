"""
统一 API 时间：输出带 Asia/Shanghai（东八区）的 ISO-8601，供前端与「北京时间」一致。

naive 字段时间含义（与当前 models / 业务写入方式一致）：
- utc：数据库里存的是「UTC 墙上时刻」的 naive（如 datetime.utcnow、SDK 卡密/日志等）
- civil：数据库里存的是「中国本地时刻」的 naive（如 get_now() 写入的 App/用户等，不经 UTC 转换）
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional
from zoneinfo import ZoneInfo

CST = ZoneInfo("Asia/Shanghai")


def to_api_beijing_iso(
    dt: Optional[datetime],
    *,
    naive: Literal["utc", "civil"] = "utc",
) -> Optional[str]:
    """
    将任意 datetime 转为「东八区」的 ISO 字符串（含 +08:00），避免前端按本地时区误解析。

    - 若已带时区：先转 Asia/Shanghai 再 isoformat
    - 若为 naive 且 naive='utc'：按 UTC 理解再转到东八区
    - 若为 naive 且 naive='civil'：按东八区「墙上时刻」标上时区后输出（不移动钟面数字）
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(CST).isoformat()
    if naive == "utc":
        return dt.replace(tzinfo=timezone.utc).astimezone(CST).isoformat()
    return dt.replace(tzinfo=CST).isoformat()


# 兼容旧名
def isoformat_utc_naive_to_cst(dt: Optional[datetime]) -> Optional[str]:
    return to_api_beijing_iso(dt, naive="utc")
