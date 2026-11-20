#!/usr/bin/env python3
"""Restart only the target TV and verify a new boot plus automatic Home/network return."""
from pathlib import Path
import socket
import subprocess
import time

ADB=Path.home()/'.local/share/google-android-tools/platform-tools/adb'
SERIAL='192.0.2.20:5555'

def shell(*args):
    return subprocess.run([str(ADB),'-s',SERIAL,'shell',*args],capture_output=True,text=True,timeout=5,check=True).stdout.strip()

if __name__=='__main__':
    original=shell('cat','/proc/sys/kernel/random/boot_id')
    try:subprocess.run([str(ADB),'-s',SERIAL,'reboot'],capture_output=True,timeout=8,check=True)
    except subprocess.TimeoutExpired:pass # The connection can disappear before the command replies.
    subprocess.run([str(ADB),'disconnect',SERIAL],capture_output=True,timeout=5)
    print('TV restart requested; waiting for automatic Tailscale reconnection.',flush=True)
    deadline=time.monotonic()+150
    last_report=0
    while time.monotonic()<deadline:
        try:
            with socket.create_connection(('192.0.2.20',5555),timeout=2):pass
            subprocess.run([str(ADB),'connect',SERIAL],capture_output=True,timeout=4)
            if shell('cat','/proc/sys/kernel/random/boot_id')!=original and shell('getprop','sys.boot_completed')=='1':
                resumed=[x for x in shell('dumpsys','activity','activities').splitlines() if 'mResumedActivity' in x]
                if any('dev.tvlivedashboard/' in x for x in resumed):
                    print('PASS: new boot, automatic Tailscale/ADB reconnection, TV Live Dashboard foreground.',flush=True)
                    break
        except (OSError,subprocess.SubprocessError):pass
        if time.monotonic()-last_report>20:
            print('Waiting for TV startup.',flush=True);last_report=time.monotonic()
        time.sleep(2)
    else:
        print('Startup still needs an on-TV check.',flush=True)
        raise SystemExit(2)
