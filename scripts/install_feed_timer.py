#!/usr/bin/env python3
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
units = Path.home() / '.config/systemd/user'
units.mkdir(parents=True, exist_ok=True)
(units / 'tv-live-dashboard-feed.service').write_text(f'''[Unit]
Description=Publish selected TV Live Dashboard display data

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 {root}/scripts/collect_feed.py
NoNewPrivileges=yes
PrivateTmp=yes
UMask=0077
''')
(units / 'tv-live-dashboard-feed.timer').write_text('''[Unit]
Description=Refresh TV Live Dashboard display data every 15 seconds

[Timer]
OnBootSec=15s
OnUnitActiveSec=15s
AccuracySec=1s
Unit=tv-live-dashboard-feed.service

[Install]
WantedBy=timers.target
''')
subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
subprocess.run(['systemctl', '--user', 'start', 'tv-live-dashboard-feed.service'], check=True)
subprocess.run(['systemctl', '--user', 'enable', '--now', 'tv-live-dashboard-feed.timer'], check=True)
for name,interpreter,script in (
    ('work','/home/your-user/Projects/jarvis-discord-bot/.venv/bin/python','collect_work.py'),
    ('codex','/usr/bin/python3','collect_codex.py'),
):
    unit='tv-live-dashboard-'+name
    (units/(unit+'.service')).write_text(f'''[Unit]
Description=Refresh TV Live Dashboard {name} display data

[Service]
Type=oneshot
ExecStart={interpreter} {root}/scripts/{script}
NoNewPrivileges=yes
PrivateTmp=no
UMask=0077
TimeoutStartSec=45s
''')
    (units/(unit+'.timer')).write_text(f'''[Unit]
Description=Refresh TV Live Dashboard {name} every five minutes

[Timer]
OnBootSec=30s
OnUnitActiveSec=5min
AccuracySec=10s
Unit={unit}.service

[Install]
WantedBy=timers.target
''')
subprocess.run(['systemctl','--user','daemon-reload'],check=True)
for name in ('work','codex'):
    subprocess.run(['systemctl','--user','enable','--now','tv-live-dashboard-'+name+'.timer'],check=True)
    subprocess.run(['systemctl','--user','start','--no-block','tv-live-dashboard-'+name+'.service'],check=True)
