#!/usr/bin/env python3
"""Publish selected display data; no Docker socket, bot database or environment access."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import time

ROOT = Path(__file__).resolve().parents[1]
BOT_DATA = Path.home() / 'Projects/jarvis-discord-bot/data'
REMINDERS = Path.home() / 'Desktop/reminder.txt'
SERVICES = {
    'jarvis-discord': 'Jarvis', 'jellyfin': 'Jellyfin',
    'download-client': 'qBittorrent', 'download-vpn': 'Download VPN',
}

def read_json(path):
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}

def age(timestamp, now):
    if isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool):
        return now - timestamp
    return None

def timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.timestamp() if parsed.tzinfo else None
    except (ValueError, TypeError):
        return None

def activity(ready, now, process_started=None):
    """Export state and timestamps only, never task events, text or identifiers."""
    progress = read_json(BOT_DATA / 'live-progress.json')
    active = progress.get('active')
    known = isinstance(active, list)
    starts = [timestamp(item.get('started_at')) for item in active or [] if isinstance(item, dict)]
    starts = [value for value in starts if value is not None and value <= now
              and (process_started is None or value >= process_started)]
    last_success = None
    try:
        # Bounded tail; a partial first record is ignored. No request text leaves this function.
        with (BOT_DATA / 'request-telemetry.jsonl').open('rb') as stream:
            stream.seek(0, 2)
            size = stream.tell()
            stream.seek(max(0, size - 1_048_576))
            if size > 1_048_576:
                stream.readline()
            for line in stream:
                try:
                    record = json.loads(line)
                    completed = timestamp(record.get('completed_at'))
                    if record.get('outcome') == 'success' and completed is not None and completed <= now:
                        last_success = max(last_success or 0, completed)
                except (ValueError, AttributeError, TypeError):
                    pass
    except OSError:
        pass
    return {'state': 'offline' if not ready else 'unknown' if not known else 'working' if starts else 'idle',
            'active_count': len(starts) if ready and known else None,
            'started_at': min(starts) if starts and ready else None,
            'last_success_at': last_success}

def storage():
    result = []
    for path, label in (('/', 'the host system'), ('/srv/storage', 'Media storage')):
        if path != '/' and not os.path.ismount(path):
            continue
        try:
            usage = shutil.disk_usage(path)
            result.append({'label': label, 'used_percent': round(100 * usage.used / usage.total, 1),
                           'free_bytes': usage.free})
        except (OSError, ZeroDivisionError):
            pass
    return result

def reminders(path):
    try:
        raw = path.read_text(encoding='utf-8')
    except OSError:
        return {'available': False, 'raw': '', 'items': [], 'unfinished': 0, 'completed': 0}
    items = []
    for line in raw.splitlines():
        match = re.match(r'^\s*(?:[-*]\s*)?\[([ xX])\]\s*(.*)$', line)
        if not match:
            continue
        text = match[2]
        priority = re.match(r'^(?:\*\*)?(?:(?:priority|p)\s*)?(\d+)[.):\s-]', text, re.I)
        items.append({'text': text, 'done': match[1].lower() == 'x',
                      'priority': int(priority[1]) if priority else None})
    items.sort(key=lambda item: (item['done'], item['priority'] if item['priority'] is not None else 999))
    return {'available': True, 'raw': raw, 'items': items,
            'unfinished': sum(not item['done'] for item in items),
            'completed': sum(item['done'] for item in items)}

def collect(now=None):
    now = time.time() if now is None else now
    heartbeat = read_json(BOT_DATA / 'jarvis-heartbeat.json')
    heartbeat_age = age(heartbeat.get('timestamp'), now)
    report = read_json(BOT_DATA / 'container-status.json')
    report_age = age(report.get('checked_at'), now)
    fresh = report_age is not None and -5 <= report_age <= 90 and report.get('docker_ok') is True
    containers = {item.get('name'): item for item in report.get('containers', []) if isinstance(item, dict)}
    services = []
    for name, label in SERVICES.items():
        source = containers.get(name, {})
        health = source.get('health', 'unknown')
        state = source.get('state', 'missing')
        online = fresh and state == 'running' and health not in ('unhealthy', 'starting')
        uptime = None
        try:
            started = datetime.fromisoformat(str(source['started_at']).replace('Z', '+00:00'))
            if started.tzinfo:
                uptime = max(0, int(now - started.timestamp()))
        except (KeyError, ValueError, TypeError):
            pass
        services.append({'id': name, 'label': label, 'online': online, 'stale': not fresh,
                         'state': state if fresh else 'stale', 'health': health if fresh else 'unknown',
                         'uptime_seconds': uptime if fresh else None})
    try:
        uptime = int(float(Path('/proc/uptime').read_text().split()[0]))
    except (OSError, ValueError, IndexError):
        uptime = None
    ready = heartbeat.get('ready') is True and heartbeat_age is not None and 0 <= heartbeat_age <= 45
    started = timestamp(containers.get('jarvis-discord', {}).get('started_at'))
    return {'schema': 1, 'collected_at': now, 'host': {'name': 'the host', 'uptime_seconds': uptime, 'storage': storage()},
            'jarvis': {'ready': ready, 'activity': activity(ready, now, started),
                       'heartbeat_age_seconds': round(heartbeat_age, 1) if heartbeat_age is not None else None},
            'services': services, 'reminders': reminders(REMINDERS)}

if __name__ == '__main__':
    destination = ROOT / 'state/feed/snapshot.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.tmp')
    temporary.write_text(json.dumps(collect(), ensure_ascii=False, allow_nan=False) + '\n')
    temporary.chmod(0o600)
    os.replace(temporary, destination)
