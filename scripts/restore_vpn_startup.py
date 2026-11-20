#!/usr/bin/env python3
"""Restore the saved pre-project always-on VPN preference on the target TV."""
import json
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[1]
adb=Path.home()/'.local/share/google-android-tools/platform-tools/adb'
base=[str(adb),'-s','192.0.2.20:5555','shell','settings']
saved=json.loads((root/'state/private/vpn-before.json').read_text())['always_on_vpn_app']
current=subprocess.check_output(base+['get','secure','always_on_vpn_app'],text=True).strip()
if current!='com.tailscale.ipn':raise SystemExit('A different VPN preference is active; leaving it unchanged.')
args=['delete','secure','always_on_vpn_app'] if saved in ('','null') else ['put','secure','always_on_vpn_app',saved]
subprocess.run(base+args,check=True)
print('Previous always-on VPN preference restored. Lockdown was not changed.')
