"""Private TV dashboard API and a separate, narrowly scoped phone signal receiver."""
import concurrent.futures
from datetime import datetime
from email.utils import parsedate_to_datetime
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import html
import json
import math
import os
from pathlib import Path
import re
import threading
import time
import urllib.request
from urllib.parse import urlencode, urlsplit
import xml.etree.ElementTree as ET

FEED = Path(os.getenv('FEED_PATH', '/feed/snapshot.json'))
TOKEN_PATH = Path(os.getenv('TOKEN_PATH', '/run/secrets/dashboard_token'))
TEAMS_CONFIG = Path(os.getenv('TEAMS_CONFIG_PATH', '/run/secrets/teams_receiver.json'))
TEAMS_STATE = Path(os.getenv('TEAMS_STATE_PATH', '/signals/teams.json'))
TEAMS_LOCK = threading.Lock()
ALLOWED_CLIENTS = frozenset(os.getenv('ALLOWED_CLIENTS', '192.0.2.20,192.0.2.10').split(','))
NEWS_FEEDS = (
    ('BBC World', 'https://feeds.bbci.co.uk/news/world/rss.xml'),
    ('Ars Technica', 'https://feeds.arstechnica.com/arstechnica/index'),
)
NEWS = {'checked_at': None, 'items': [], 'unavailable_sources': []}
WEATHER = {'available': False, 'checked_at': None, 'location': 'Lakeview', 'unit': '°F'}
# Public provider status only; these requests never use the private calendar feed.
OUTAGE_SOURCES = (
    ('Microsoft 365', 'https://status.cloud.microsoft/api/posts/mac', 'microsoft', 'https://status.cloud.microsoft/'),
    ('Azure', 'https://status.cloud.microsoft/api/posts/azure', 'microsoft', 'https://status.cloud.microsoft/'),
    ('OpenAI', 'https://status.openai.com/history.rss', 'rss', 'https://status.openai.com/'),
    ('Discord', 'https://discordstatus.com/api/v2/incidents/unresolved.json', 'statuspage', 'https://discordstatus.com/'),
    ('Tailscale', 'https://status.tailscale.com/history.rss', 'rss', 'https://status.tailscale.com/'),
    ('Cloudflare', 'https://www.cloudflarestatus.com/api/v2/incidents/unresolved.json', 'statuspage', 'https://www.cloudflarestatus.com/'),
)
OUTAGES = {'checked_at': None, 'items': [], 'unavailable_sources': [], 'source_count': len(OUTAGE_SOURCES)}
LOCK = threading.Lock()

def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def teams_config():
    try:
        value = json.loads(TEAMS_CONFIG.read_text())
        if not isinstance(value, dict) or not isinstance(value.get('token'), str) or len(value['token']) < 32:
            return {}
        if not isinstance(value.get('allowed_clients'), list) or not value['allowed_clients']:
            return {}
        return value
    except (OSError, ValueError):
        return {}

def teams_status():
    """Only a flag and server timestamps cross into the display API."""
    try:
        value = json.loads(TEAMS_STATE.read_text())
        if not isinstance(value, dict):
            value = {}
    except (OSError, ValueError):
        value = {}
    event_at = value.get('last_event_at')
    received_at = value.get('last_received_at')
    initialized = number(event_at) and event_at > 0
    return {'configured': bool(teams_config()), 'initialized': bool(initialized),
            'pending': bool(initialized and value.get('pending') is True),
            'last_event_at': event_at if initialized else None,
            'last_received_at': received_at if number(received_at) and received_at > 0 else None}

def record_teams_signal(event):
    with TEAMS_LOCK:
        previous = teams_status()
        now = time.time()
        received = previous['last_received_at']
        if event == 'received':
            received = max(now, (received or 0) + .000001)
        state = {'schema': 1, 'last_event_at': now, 'last_received_at': received, 'pending': event == 'received'}
        TEAMS_STATE.parent.mkdir(parents=True, exist_ok=True)
        temporary = TEAMS_STATE.with_suffix('.tmp')
        temporary.write_text(json.dumps(state, allow_nan=False) + '\n')
        temporary.chmod(0o600)
        os.replace(temporary, TEAMS_STATE)

def select_weather(payload, now):
    """The forecast endpoint is explicitly requested in Fahrenheit and mph."""
    current, daily = payload.get('current', {}), payload.get('daily', {})
    if payload.get('current_units', {}).get('temperature_2m') != '°F':
        raise ValueError('Unexpected temperature unit')
    required = ('time', 'temperature_2m', 'apparent_temperature', 'weather_code', 'wind_speed_10m')
    if not all(number(current.get(key)) for key in required) or not -300 <= now-current['time'] <= 3600:
        raise ValueError('Missing or old current conditions')
    def first(key):
        values = daily.get(key, [])
        return values[0] if values and number(values[0]) else None
    return {'available': True, 'checked_at': now, 'observed_at': current['time'],
            'location': 'Lakeview', 'unit': '°F', 'provider': 'Open-Meteo',
            'temperature': current['temperature_2m'], 'feels_like': current['apparent_temperature'],
            'code': current['weather_code'], 'wind_mph': current['wind_speed_10m'],
            'high': first('temperature_2m_max'), 'low': first('temperature_2m_min'),
            'rain_chance': first('precipitation_probability_max'), 'refresh_failed': False}

def fetch_weather():
    location = json.loads((FEED.parent / 'weather-location.json').read_text())
    query = urlencode({'latitude': float(location['latitude']), 'longitude': float(location['longitude']),
        'current': 'temperature_2m,apparent_temperature,weather_code,wind_speed_10m',
        'daily': 'temperature_2m_max,temperature_2m_min,precipitation_probability_max',
        'temperature_unit': 'fahrenheit', 'wind_speed_unit': 'mph', 'precipitation_unit': 'inch',
        'timeformat': 'unixtime', 'timezone': 'America/Chicago', 'forecast_days': 2})
    request = urllib.request.Request('https://api.open-meteo.com/v1/forecast?' + query,
                                    headers={'User-Agent': 'JarvisHome/0.1 (personal weather display)'})
    with urllib.request.urlopen(request, timeout=12) as response:
        body = response.read(200_001)
    if len(body) > 200_000:
        raise ValueError('Weather response too large')
    return select_weather(json.loads(body), time.time())

def update_weather():
    while True:
        try:
            selected = fetch_weather()
            with LOCK:
                WEATHER.update(selected)
        except Exception:
            with LOCK:
                WEATHER['refresh_failed'] = True
        time.sleep(600)

def useful_alerts(snapshot, now):
    alerts = []
    def add(key, message, severity='warning'):
        alerts.append({'id': key, 'message': message, 'severity': severity})
    if snapshot.get('feed_stale'):
        add('feed', 'Home server status is out of date')
        return alerts
    services = snapshot.get('services', [])
    if not services or any(service.get('stale') for service in services):
        add('services-stale', 'Service monitoring is out of date')
    for service in services:
        if not service.get('stale') and not service.get('online'):
            add(service['id'], service['label'] + ' is unavailable', 'critical')
    jarvis = snapshot.get('jarvis', {})
    if not jarvis.get('ready') and any(s.get('id') == 'jarvis-discord' and s.get('online') for s in services):
        add('jarvis-heartbeat', 'Jarvis is running but its heartbeat is missing')
    for disk in snapshot.get('host', {}).get('storage', []):
        if number(disk.get('used_percent')) and disk['used_percent'] >= 90:
            add('storage-' + disk['label'], disk['label'] + ' is ' + str(round(disk['used_percent'])) + '% full',
                'critical' if disk['used_percent'] >= 97 else 'warning')
    for name, limit in (('work', 600), ('codex', 900), ('weather', 1800)):
        data = snapshot.get(name, {})
        fresh = data.get('available') and not data.get('refresh_failed') and number(data.get('checked_at')) and -5 <= now-data['checked_at'] < limit
        if not fresh:
            add(name + '-stale', {'work': 'Work calendar', 'codex': 'Codex usage', 'weather': 'Local weather'}[name] + ' needs an update')
        if name == 'codex' and fresh:
            for window in data.get('windows', []):
                used, resets = window.get('used_percent'), window.get('resets_at')
                if number(used) and used >= 90 and number(resets) and resets > now:
                    minutes = window.get('window_minutes', 0)
                    label = str(round(minutes/60))+'h' if minutes < 1440 else str(round(minutes/1440))+'d'
                    add('codex-' + label, 'Codex ' + label + ' limit: ' + str(round(used)) + '% used', 'critical' if used >= 100 else 'warning')
    return alerts

def clean_text(value, limit=250):
    return ' '.join(html.unescape(re.sub(r'<[^>]*>', '', value or '')).split())[:limit]

def outage_time(value):
    if not isinstance(value,str):
        return None
    try:
        date=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:
        try:
            date=parsedate_to_datetime(value)
        except (ValueError,TypeError):
            return None
    return date.timestamp() if date.tzinfo is not None else None

def select_outages(source, kind, payload, homepage, now):
    """Select active reports with attribution; never infer a global outage from a failed check."""
    items=[]
    def add(title,status,updated,link=None,severity='warning'):
        title=clean_text(title,200)
        if not title:
            raise ValueError('Missing incident title')
        candidate=link or homepage
        parts=urlsplit(candidate)
        url=candidate if parts.scheme=='https' and parts.hostname==urlsplit(homepage).hostname and not parts.username and not parts.password else homepage
        items.append({'source':source,'title':title,'status':status,'updated_at':outage_time(updated),
                      'url':url,'severity':severity,'checked_at':now})
    if kind=='microsoft':
        status=payload.get('Status')
        if status in ('Available','Operational'):
            return []
        if status not in ('Service degradation','Service interruption','Extended recovery'):
            raise ValueError('Unknown provider status')
        add(payload.get('Title'),status,payload.get('LastUpdatedTime'),severity='critical' if status=='Service interruption' else 'warning')
    elif kind=='statuspage':
        if not isinstance(payload.get('incidents'),list):
            raise ValueError('Missing incident list')
        for incident in payload['incidents'][:30]:
            if incident.get('status') in ('investigating','identified','monitoring'):
                add(incident.get('name'),incident['status'].capitalize(),incident.get('updated_at'),incident.get('shortlink'),
                    'critical' if incident.get('impact') in ('major','critical') else 'warning')
    elif kind=='rss':
        root=ET.fromstring(payload)
        if root.tag!='rss' or root.find('channel') is None:
            raise ValueError('Not a status RSS feed')
        for item in root.findall('./channel/item')[:30]:
            # Provider RSS explicitly labels each latest incident state. Resolved history is excluded.
            description=clean_text(re.sub(r'<[^>]*>',' ',item.findtext('description') or ''))
            match=re.match(r'^Status:\s*(Investigating|Identified|Monitoring|Resolved|Postmortem)\b',description)
            if not match:
                raise ValueError('Unknown status RSS state')
            if match[1] in ('Investigating','Identified','Monitoring'):
                add(item.findtext('title'),match[1],item.findtext('pubDate'),item.findtext('link'))
    else:
        raise ValueError('Unknown status format')
    return items

def fetch_outages(source):
    label,url,kind,homepage=source
    request=urllib.request.Request(url,headers={'User-Agent':'JarvisHome/0.1 (personal service-status display)'})
    with urllib.request.urlopen(request,timeout=10) as response:
        body=response.read(2_000_001)
    if len(body)>2_000_000:
        raise ValueError('Status response too large')
    return select_outages(label,kind,body if kind=='rss' else json.loads(body),homepage,time.time())

def refresh_outages(previous):
    current={}
    failed=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures=[(source[0],pool.submit(fetch_outages,source)) for source in OUTAGE_SOURCES]
        for label,future in futures:
            try:
                current[label]=future.result()
            except Exception:
                failed.append(label)
                current[label]=previous.get(label,[])
    now=time.time()
    # An expired or failed feed never becomes an all-clear message.
    items=[item for label,_,_,_ in OUTAGE_SOURCES for item in current[label]
           if number(item.get('checked_at')) and -5<=now-item['checked_at']<3600]
    with LOCK:
        OUTAGES.update(checked_at=now,items=items[:30],unavailable_sources=failed)
    return current

def update_outages():
    previous={}
    while True:
        previous=refresh_outages(previous)
        time.sleep(300)

def fetch_news(source):
    label, url = source
    request = urllib.request.Request(url, headers={'User-Agent': 'JarvisHome/0.1 (personal RSS display)'})
    with urllib.request.urlopen(request, timeout=8) as response:
        body = response.read(2_000_001)
    if len(body) > 2_000_000:
        raise ValueError('Feed exceeds maximum size')
    root = ET.fromstring(body)
    return [{'title': clean_text(item.findtext('title')), 'source': label}
            for item in root.findall('.//item')[:5] if clean_text(item.findtext('title'))]

def update_news():
    while True:
        sources, failed = [], []
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [(label, pool.submit(fetch_news, (label, url))) for label, url in NEWS_FEEDS]
            for label, future in futures:
                try:
                    sources.append(future.result())
                except Exception:
                    failed.append(label)
        items = [source[index] for index in range(5) for source in sources if index < len(source)]
        with LOCK:
            if items:
                NEWS.update(checked_at=time.time(), items=items)
            NEWS['unavailable_sources'] = failed
        time.sleep(900)

def dashboard():
    try:
        snapshot = json.loads(FEED.read_text())
        if not isinstance(snapshot, dict):
            raise ValueError('Invalid snapshot')
    except (OSError, ValueError):
        snapshot = {'schema': 1, 'collected_at': None, 'services': [], 'reminders': {'available': False}}
    now = time.time()
    collected = snapshot.get('collected_at')
    snapshot['feed_stale'] = not isinstance(collected, (int, float)) or not -5 <= now - collected <= 60
    snapshot['served_at'] = now
    for name in ('work','codex'):
        try:
            value=json.loads((FEED.parent / (name+'.json')).read_text())
            if not isinstance(value,dict):raise ValueError('Invalid selected data')
        except (OSError,ValueError):
            value={'available':False,'checked_at':None}
        snapshot[name]=value
    with LOCK:
        snapshot['news'] = dict(NEWS)
        snapshot['weather'] = dict(WEATHER)
        snapshot['outages'] = dict(OUTAGES)
    snapshot['alerts'] = useful_alerts(snapshot, now)
    snapshot['teams'] = teams_status()
    return snapshot

class Handler(BaseHTTPRequestHandler):
    server_version = 'JarvisHome'
    sys_version = ''

    def log_message(self, format, *args):
        # Do not log request paths, authorization headers or display contents.
        pass

    def respond(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/healthz':
            self.respond(200, {'ok': True})
            return
        supplied = self.headers.get('Authorization', '')
        expected = 'Bearer ' + self.server.token
        if self.client_address[0] not in ALLOWED_CLIENTS or not hmac.compare_digest(supplied, expected):
            print('API access denied: client=' + self.client_address[0] +
                  ' allowed_source=' + str(self.client_address[0] in ALLOWED_CLIENTS) +
                  ' valid_token=' + str(hmac.compare_digest(supplied, expected)), flush=True)
            self.respond(403, {'error': 'Forbidden'})
            return
        if self.path != '/api/dashboard':
            self.respond(404, {'error': 'Not found'})
            return
        self.respond(200, dashboard())

    def do_POST(self):
        self.respond(405, {'error': 'Read-only service'})

class TeamsSignalHandler(Handler):
    """Port 8770 accepts fixed received/clear events, never message contents."""
    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def do_GET(self):
        config = teams_config()
        if self.client_address[0] not in config.get('allowed_clients', []):
            self.respond(403, {'error': 'Forbidden'})
            return
        nonce = config.get('setup_nonce', '')
        expires = config.get('setup_expires_at')
        if (not nonce or not number(expires) or time.time() >= expires
                or not hmac.compare_digest(self.path.encode(), ('/setup/' + nonce).encode())):
            self.respond(404, {'error': 'Not found'})
            return
        # No JavaScript, request echoes, third-party assets or credential logging.
        endpoint = html.escape(str(config.get('receiver_url', '')), quote=True)
        token = html.escape(config['token'], quote=True)
        body = ('''<!doctype html><html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Jarvis Teams setup</title><style>body{font:18px/1.6 system-ui;background:#101e2e;color:#f0f5fa;padding:24px;max-width:650px;margin:auto}input{box-sizing:border-box;width:100%;font:16px monospace;padding:12px;background:#1c3045;color:white;border:1px solid #6d879e;border-radius:8px}h1{font-size:28px}small{color:#bdcbd9}</style>
<h1>Teams → Jarvis</h1><p>This shortcut sends a fixed signal only. Do not pass Shortcut Input or notification text.</p>
<p>1. Add <b>Get Contents of URL</b> in Shortcuts. Use this URL:</p><input aria-label="Receiver URL" readonly value="''' + endpoint + '''">
<p>2. Set Method to <b>POST</b>. Add a header named <b>Authorization</b> with this value:</p><input aria-label="Authorization header" readonly value="Bearer ''' + token + '''">
<p>3. Set Request Body to <b>JSON</b>. Add one Text field: <b>event</b> = <b>received</b>.</p>
<p>4. Add a <b>Notification</b> automation for <b>Microsoft Teams</b>. Enable automatic running, including while locked if offered. Run once manually and allow the connection.</p>
<p>The TV badge appears within about 15 seconds while Home is open. Dismiss it on the TV after checking Teams.</p>
<p>Optional: create a second shortcut with <b>event</b> = <b>clear</b> and an App automation when Teams opens. This clears the signal; it does not verify all messages were read.</p>
<small>This private setup page expires automatically. Keep Tailscale connected. Only notifications delivered to this iPhone generate signals.</small></html>''').encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; form-action 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        config = teams_config()
        if not config or self.client_address[0] not in config.get('allowed_clients', []):
            self.respond(403, {'error': 'Forbidden'})
            return
        # Scheme is case-insensitive; surrounding whitespace is common when pasting on iPhone.
        supplied = self.headers.get('Authorization', '').strip()
        parts = supplied.split(None, 1)
        if not supplied:
            self.respond(403, {'error': 'Authorization header missing',
                               'hint': 'Add the Authorization header from the private setup page.'})
            return
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            self.respond(403, {'error': 'Authorization header format incorrect',
                               'hint': 'Copy the entire value, including Bearer and the space before the key.'})
            return
        if not hmac.compare_digest(parts[1].strip().encode(), config['token'].encode()):
            self.respond(403, {'error': 'Receiver key does not match',
                               'hint': 'Select All and copy the full Authorization value from the private setup page.'})
            return
        if self.path != '/teams':
            self.respond(404, {'error': 'Not found'})
            return
        if self.headers.get('Transfer-Encoding') or self.headers.get_content_type() != 'application/json':
            self.respond(400, {'error': 'A fixed JSON event is required'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            length = 0
        if not 1 <= length <= 128:
            self.respond(413, {'error': 'Event size must be 1 to 128 bytes'})
            return
        try:
            event = json.loads(self.rfile.read(length))
            if (not isinstance(event, dict) or set(event) != {'event'}
                    or event['event'] not in ('received', 'clear')):
                raise ValueError('Invalid event')
        except (ValueError, UnicodeError):
            self.respond(400, {'error': 'Only received or clear events are accepted'})
            return
        try:
            record_teams_signal(event['event'])
        except OSError:
            self.respond(503, {'error': 'Signal storage unavailable'})
            return
        self.respond(200, {'ok': True})

if __name__ == '__main__':
    token = TOKEN_PATH.read_text().strip()
    if len(token) < 32:
        raise SystemExit('A dashboard token of at least 32 characters is required')
    server = ThreadingHTTPServer((os.getenv('LISTEN_ADDRESS', '127.0.0.1'), 8768), Handler)
    server.token = token
    if teams_config():
        receiver = ThreadingHTTPServer((os.getenv('LISTEN_ADDRESS', '127.0.0.1'), 8770), TeamsSignalHandler)
        threading.Thread(target=receiver.serve_forever, daemon=True).start()
        print('Private Teams signal receiver listening on port 8770', flush=True)
    threading.Thread(target=update_news, daemon=True).start()
    threading.Thread(target=update_weather, daemon=True).start()
    threading.Thread(target=update_outages, daemon=True).start()
    print('TV Live Dashboard read-only API listening on port 8768', flush=True)
    server.serve_forever()
