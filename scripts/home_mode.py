#!/usr/bin/env python3
"""Switch only this TV's launcher accessibility services; preserve all other services."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
ADB = Path.home() / '.local/share/google-android-tools/platform-tools/adb'
SERIAL = '192.0.2.20:5555'
JARVIS = 'dev.tvlivedashboard/dev.tvlivedashboard.HomeService'
PROJECTIVY = 'com.spocky.projengmenu/com.spocky.projengmenu.services.ProjectivyAccessibilityService'

def shell(*args):
    return subprocess.run([str(ADB), '-s', SERIAL, 'shell', *args], check=True, capture_output=True, text=True, timeout=20).stdout.strip()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['jarvis','projectivy'])
    args = parser.parse_args()
    current = shell('settings','get','secure','enabled_accessibility_services')
    record = ROOT / 'state/private/home-before-jarvis.json'
    if not record.exists():
        record.write_text(json.dumps({'timestamp':datetime.now().astimezone().isoformat(), 'services':current},indent=2)+'\n')
        record.chmod(0o600)
    services = [x for x in current.split(':') if x and x != 'null' and x not in (JARVIS,PROJECTIVY)]
    services.append(JARVIS if args.mode == 'jarvis' else PROJECTIVY)
    shell('settings','put','secure','enabled_accessibility_services',':'.join(services))
    shell('settings','put','secure','accessibility_enabled','1')
    package = 'dev.tvlivedashboard/.MainActivity' if args.mode == 'jarvis' else 'com.spocky.projengmenu/.ui.home.MainActivity'
    shell('am','start','-n',package)
    print('Home override selected:', args.mode)
    print('Google launcher and Projectivy remain installed and enabled.')
