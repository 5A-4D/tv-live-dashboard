#!/usr/bin/env python3
"""Install/update this app on the explicitly named Google TV only."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
adb = Path.home() / '.local/share/google-android-tools/platform-tools/adb'
serial = '192.0.2.20:5555'
subprocess.run([str(adb), '-s', serial, 'install', '-r', str(root / 'build/tv-live-dashboard.apk')], check=True)
subprocess.run([str(adb), '-s', serial, 'shell', 'am', 'start', '-n', 'dev.tvlivedashboard/.MainActivity'], check=True)
