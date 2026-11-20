#!/usr/bin/env python3
"""Create fresh local example credentials for an APK build; never copy live state."""
import argparse
import json
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', default='http://192.0.2.10:8768/api/dashboard')
    args = parser.parse_args()
    private = ROOT / 'state/private'
    private.mkdir(parents=True, exist_ok=True, mode=0o700)
    private.chmod(0o700)
    config = private / 'tv-config.json'
    if config.exists():
        raise SystemExit('A build configuration already exists; inspect it before replacing it.')
    token = secrets.token_urlsafe(32)
    config.write_text(json.dumps({'endpoint': args.endpoint, 'token': token, 'debug': False}) + '\n')
    config.chmod(0o600)
    for name, value in [('dashboard_token', token), ('signing_password', secrets.token_urlsafe(32))]:
        path = private / name
        with path.open('x') as stream:
            stream.write(value + '\n')
        path.chmod(0o600)
    receiver = private / 'teams_receiver.json'
    if not receiver.exists():
        receiver.write_text('{}\n')
        receiver.chmod(0o600)
    for name in ['feed', 'signals']:
        (ROOT / 'state' / name).mkdir(parents=True, exist_ok=True, mode=0o700)
    print('Fresh example build configuration created under ignored state/private/. No credentials printed.')


if __name__ == '__main__':
    main()
