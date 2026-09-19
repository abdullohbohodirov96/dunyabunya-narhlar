"""Vaqt jadvali — kuniga bir necha marta post, eslatma va kunlik hisobot."""
import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

import db
import poster
from config import SELF_URL, TZ

log = logging.getLogger("scheduler")
_sched: AsyncIOScheduler | None = None
_bot: Bot | None = None


def parse_times(raw: str) -> list[tuple[int, int]]:
    out = []
    for chunk in (raw or "").replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            h, m = chunk.split(":")
            h, m = int(h), int(m)
            if 0 <= h < 24 and 0 <= m < 60:
                out.append((h, m))
        except ValueError:
            continue
    return sorted(set(out))


WEEKDAYS = {
    "dush": "mon", "sesh": "tue", "chor": "wed", "pay": "thu",
    "jum": "fri", "shan": "sat", "yak": "sun",
    "mon": "mon", "tue": "tue", "wed": "wed", "thu": "thu",
    "fri": "fri", "sat": "sat", "sun": "sun",
}


def parse_weekly(raw: str):
    """'dush 10:00' -> ('mon', 10, 0). Xato bo'lsa None."""
    parts = (raw or "").strip().lower().split()
    if len(parts) != 2:
        return None
    day = WEEKDAYS.get(parts[0][:4]) or WEEKDAYS.get(parts[0][:3])
    times = parse_times(parts[1])
    if not day or not times:
        return None
    return day, times[0][0], times[0][1]


def start(bot: Bot) -> AsyncIOScheduler:
    global _sched, _bot
    _bot = bot
    _sched = AsyncIOScheduler(timezone=TZ)
    _sched.start()
    return _sched


async def reload_jobs() -> list[tuple[int, int]]:
    """Sozlamadagi vaqtlarga qarab barcha ishlarni qayta qo'yadi."""
    assert _sched and _bot
    for job in _sched.get_jobs():
        job.remove()

    settings = await db.all_settings()
    times = parse_times(settings.get("post_times", ""))
    for h, m in times:
        _sched.add_job(
            poster.post_next,
            CronTrigger(hour=h, minute=m, timezone=TZ),
            args=[_bot],
            id=f"post_{h:02d}{m:02d}",
            misfire_grace_time=1800,   # server uxlab qolsa, 30 daq ichida baribir joylaydi
            coalesce=True,
            max_instances=1,
        )

    minutes = max(1, int(settings.get("remind_every_min", "5") or 5))
    _sched.add_job(
        poster.alert_empty,
        IntervalTrigger(minutes=minutes, timezone=TZ),
        args=[_bot],
        id="alert",
        coalesce=True,
        max_instances=1,
    )

    if SELF_URL:
        _sched.add_job(
            keep_awake,
            IntervalTrigger(minutes=10, timezone=TZ),
            id="keepalive",
            coalesce=True,
            max_instances=1,
        )

    rh, rm = poster._hm(settings.get("report_at", "21:00"), (21, 0))
    _sched.add_job(
        poster.daily_report,
        CronTrigger(hour=rh, minute=rm, timezone=TZ),
        args=[_bot],
        id="report",
        misfire_grace_time=3600,
        coalesce=True,
    )

    weekly = parse_weekly(settings.get("pricebook_at", ""))
    if weekly:
        day, wh, wm = weekly
        _sched.add_job(
            poster.post_pricebook,
            CronTrigger(day_of_week=day, hour=wh, minute=wm, timezone=TZ),
            args=[_bot],
            id="pricebook",
            misfire_grace_time=7200,
            coalesce=True,
        )

    log.info("Jadval yangilandi: %s (prays: %s)", times, weekly)
    return times


async def keep_awake() -> None:
    """O'ziga so'rov yuboradi — Render servisni uxlatmasligi uchun."""
    import aiohttp

    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.get(f"{SELF_URL}/health") as r:
                log.debug("keep-awake: %s", r.status)
    except Exception as e:
        log.warning("keep-awake ishlamadi: %s", e)


def next_runs(limit: int = 6) -> list[str]:
    if not _sched:
        return []
    jobs = [j for j in _sched.get_jobs() if j.id.startswith("post_") and j.next_run_time]
    jobs.sort(key=lambda j: j.next_run_time)
    return [f"{j.next_run_time:%d.%m %H:%M}" for j in jobs[:limit]]
