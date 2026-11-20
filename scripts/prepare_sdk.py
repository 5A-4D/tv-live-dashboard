#!/usr/bin/env python3
"""Download Android build tools from Google's signed HTTPS repository metadata."""
import concurrent.futures
import hashlib
import io
import os
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path.home() / '.cache/jarvis-tv-sdk'
BASE = 'https://dl.google.com/android/repository/'

def download(url):
    with urllib.request.urlopen(url, timeout=90) as response:
        return response.read()

def install(item):
    name, archive, directory, marker = item
    destination = ROOT / directory
    if (destination / marker).exists():
        return f'{name}: already present'
    url = archive.findtext('url')
    expected = archive.findtext('checksum')
    checksum_type = archive.find('checksum').get('type', 'sha1')
    body = download(BASE + url)
    if hashlib.new(checksum_type, body).hexdigest() != expected:
        raise RuntimeError(f'{name}: checksum mismatch')
    with zipfile.ZipFile(io.BytesIO(body)) as bundle:
        for member in bundle.infolist():
            parts = Path(member.filename).parts
            if Path(member.filename).is_absolute() or '..' in parts:
                raise RuntimeError('Unsafe SDK archive path')
        roots = {Path(m.filename).parts[0] for m in bundle.infolist() if Path(m.filename).parts}
        if len(roots) != 1:
            raise RuntimeError('Unexpected SDK archive layout')
        prefix = roots.pop()
        destination.mkdir(parents=True, exist_ok=True)
        for member in bundle.infolist():
            relative = Path(member.filename).relative_to(prefix)
            if not relative.parts:
                continue
            target = destination / relative
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(bundle.read(member))
                mode = (member.external_attr >> 16) & 0o777
                target.chmod(mode or 0o644)
    return f'{name}: installed and checksum verified'

if __name__ == '__main__':
    ROOT.mkdir(parents=True, exist_ok=True)
    if (ROOT / 'platform/android.jar').is_file() and (ROOT / 'build-tools/aapt').is_file():
        print('Android SDK: using verified local cache', flush=True)
        raise SystemExit(0)
    repository = ET.fromstring(download(BASE + 'repository2-1.xml'))
    for element in repository.iter():
        element.tag = element.tag.split('}')[-1]
    wanted = {'platforms;android-34': ('platform', 'platform', 'android.jar'),
              'build-tools;34.0.0': ('build-tools', 'build-tools', 'aapt')}
    jobs = []
    selected = set()
    for package in repository.findall('remotePackage'):
        if package.get('path') not in wanted or package.get('path') in selected:
            continue
        name, directory, marker = wanted[package.get('path')]
        for archive in package.findall('archives/archive'):
            if archive.findtext('host-os') in (None, 'linux'):
                jobs.append((name, archive.find('complete'), directory, marker))
                selected.add(package.get('path'))
                break
    if len(jobs) != 2:
        raise RuntimeError('Required SDK packages not found in Google metadata')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for result in pool.map(install, jobs):
            print(result, flush=True)
