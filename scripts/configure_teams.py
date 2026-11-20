#!/usr/bin/env python3
"""Pair one phone with the metadata-only Teams receiver; never print its key."""
import argparse
import ipaddress
import json
from pathlib import Path
import secrets
import time

ROOT = Path(__file__).resolve().parents[1]

def configure(phone_ip):
    address = ipaddress.ip_address(phone_ip)
    if address not in ipaddress.ip_network('100.64.0.0/10'):
        raise ValueError('Use the phone’s Tailscale IPv4 address')
    path = ROOT / 'state/private/teams_receiver.json'
    try:
        old = json.loads(path.read_text())
    except (OSError, ValueError):
        old = {}
    config = {'token': old.get('token') or secrets.token_urlsafe(32),
              'allowed_clients': ['192.0.2.10', str(address)],
              'receiver_url': 'http://192.0.2.10:8770/teams',
              'setup_nonce': secrets.token_urlsafe(24), 'setup_expires_at': time.time() + 3600}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, allow_nan=False) + '\n')
    path.chmod(0o600)
    signals = ROOT / 'state/signals'
    signals.mkdir(parents=True, exist_ok=True)
    signals.chmod(0o700)
    # The setup link is an expiring capability, not the permanent receiver key.
    return 'http://192.0.2.10:8770/setup/' + config['setup_nonce']

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phone-ip', required=True)
    args = parser.parse_args()
    print(configure(args.phone_ip))
