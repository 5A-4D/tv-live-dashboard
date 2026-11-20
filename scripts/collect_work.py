#!/usr/bin/env python3
"""Read the private feed in memory through the existing reader; publish anonymous intervals only."""
import asyncio
from datetime import datetime, time, timedelta
import json
import math
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
BOT = Path.home() / 'Projects/jarvis-discord-bot'
# Owner's dashboard-only recurring morning meeting, relative to the configured work start.
MORNING_BLOCK_MINUTES = 60

def anonymous_days(availability, today, zone, work_start, work_end):
    days = []
    for offset in range(7):
        day = today + timedelta(days=offset)
        first = datetime.combine(day, time.fromisoformat(work_start), zone)
        last = datetime.combine(day, time.fromisoformat(work_end), zone)
        working = day.weekday() < 5
        intervals = [(max(m.start, first), min(m.end, last)) for m in availability.meetings
                     if working and m.start < last and m.end > first]
        if working:
            intervals.append((first, min(last, first + timedelta(minutes=MORNING_BLOCK_MINUTES))))
        if working and any(a <= day < b for a, b in availability.all_day):
            intervals.append((first,last))
        merged = []
        for a,b in sorted(intervals):
            if a >= b: continue
            if merged and a <= merged[-1][1]: merged[-1] = (merged[-1][0], max(b,merged[-1][1]))
            else: merged.append((a,b))
        days.append({'date':day.isoformat(), 'working':working, 'start':first.timestamp(),
                     'end':last.timestamp(), 'busy':[{'start':a.timestamp(),'end':b.timestamp()} for a,b in merged]})
    return days

async def collect():
    from dotenv import dotenv_values
    sys.path.insert(0,str(BOT))
    from jarvis_bot.work_calendar import ScheduleQuery, read_availability
    settings = dotenv_values(BOT / '.env')
    zone_name = settings.get('WORK_CALENDAR_TIMEZONE') or 'America/Chicago'
    zone = ZoneInfo(zone_name)
    today = datetime.now(zone).date()
    fingerprints = frozenset(x.strip().lower() for x in (settings.get('WORK_CALENDAR_FREE_SERIES_SHA256') or '').split(',') if x.strip())
    # URL and raw calendar remain exclusively in this process's memory.
    availability = await read_availability(settings.get('WORK_CALENDAR_ICS_URL') or '', ScheduleQuery(today,7), zone_name,
                                           free_series_hashes=fingerprints)
    start = settings.get('WORK_DAY_START') or '08:30'
    end = settings.get('WORK_DAY_END') or '16:00'
    return {'available':True, 'checked_at':datetime.now().timestamp(), 'timezone':zone_name,
            'days':anonymous_days(availability,today,zone,start,end)}

def saved_work(path):
    """Restore only the anonymous schema; never forward arbitrary cached fields."""
    try:
        value=json.loads(path.read_text())
        number=lambda n:isinstance(n,(int,float)) and not isinstance(n,bool) and math.isfinite(n)
        if value.get('available') is not True or not number(value.get('checked_at')):
            return None
        zone=ZoneInfo(value['timezone'])
        days=[]
        for day in value['days']:
            date=datetime.fromisoformat(day['date']).date().isoformat()
            if (not isinstance(day['working'],bool) or not number(day['start'])
                    or not number(day['end']) or day['end']<=day['start']):
                return None
            busy=[]
            for interval in day['busy']:
                if (not number(interval['start']) or not number(interval['end'])
                        or not day['start']<=interval['start']<interval['end']<=day['end']):
                    return None
                busy.append({'start':interval['start'],'end':interval['end']})
            days.append({'date':date,'working':day['working'],'start':day['start'],'end':day['end'],'busy':busy})
        if not days or len(days)>7:
            return None
        return {'available':True,'checked_at':value['checked_at'],'timezone':str(zone),'days':days}
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        return None

def write_snapshot(path,result):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(result,allow_nan=False)+'\n')
    temporary.chmod(0o600)
    os.replace(temporary,path)

def refresh(path):
    backup=path.with_name('work-last-good.json')
    try:
        result=asyncio.run(collect())
    except Exception:
        # Exception text and tracebacks can contain private calendar credentials/content.
        result=saved_work(backup) or saved_work(path)
        if result:
            # Preserve the successful fetch time; old availability must not look current.
            result['refresh_failed']=True
        else:
            result={'available':False,'checked_at':None,'days':[],'refresh_failed':True}
    else:
        write_snapshot(backup,result)
    write_snapshot(path,result)
    return result

if __name__ == '__main__':
    os.umask(0o077)
    result=refresh(ROOT/'state/feed/work.json')
    status='saved schedule; refresh failed' if result.get('refresh_failed') and result['available'] else 'updated' if result['available'] else 'unavailable'
    print('Anonymous work availability:',status)
