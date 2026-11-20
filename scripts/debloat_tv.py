#!/usr/bin/env python3
"""Recorded, reversible package disabling on the explicitly selected Hisense TV."""
import argparse
import concurrent.futures
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
ADB=Path.home()/'.local/share/google-android-tools/platform-tools/adb'
SERIAL='192.0.2.20:5555'
STAGES={
    'apps': {
        'com.amazon.amazonvideo.livingroom':'Prime Video',
        'com.netflix.ninja':'Netflix',
        'com.hulu.livingroomplus':'Hulu',
        'com.disney.disneyplus':'Disney+',
        'com.instagram.airwave':'Instagram TV shortcut',
        'com.google.android.youtube.tvunplugged':'YouTube TV subscription app',
        'com.google.android.youtube.tvmusic':'YouTube Music',
        'com.google.android.play.games':'Google Play Games',
        'com.tubitv':'Tubi',
        'tv.pluto.android':'Pluto TV',
        'com.haystack.android':'Haystack News',
        'net.vidaatv.hisense.android.tv':'VIDAA Channels',
        'com.hisense.odinbrowser':'Hisense browser',
    },
    'extras': {
        'com.vt.tv.evservice':'Hisense ACR viewing-data service',
        'com.google.android.partnersetup':'Google OEM partner setup helper',
        'com.google.android.feedback':'Google feedback uploader',
        'com.google.android.syncadapters.calendar':'TV Google Calendar sync adapter; dashboard calendar runs on the host',
        'android.autoinstalls.config.google.gtvpai':'OEM suggested-app auto-install configuration',
        'com.vidaa.oemtabcontentprovider':'VIDAA recommendation content provider',
        'com.vt.hishow':'Family Moment photo/content app',
        'com.vt.tv.protector':'Hisense Device Assistant cleaner/turbo app',
        'com.vt.storemode':'Retail/store demo mode',
        'com.vt.fte':'Completed Hisense first-time experience',
        'com.vt.alexa':'Hisense Alexa; Google Assistant retained',
        'com.netflix.tokenmanager':'Unused Netflix authentication helper',
    },
}
PROTECTED={
    'dev.tvlivedashboard','com.tailscale.ipn','org.jellyfin.androidtv','com.google.android.youtube.tv',
    'com.spocky.projengmenu','com.google.android.apps.tv.launcherx','com.google.android.tungsten.setupwraith',
    'com.android.tv.settings','com.android.vending','com.google.android.webview','com.google.android.gms',
    'com.google.android.gsf','com.google.android.katniss','com.google.android.tts','com.google.android.apps.mediashell',
    'com.google.android.tv.remote.service','com.google.android.apps.tv.dreamx','com.android.bluetooth',
    'com.vt.tv.aiot','com.vt.tv.smartsense','com.vt.tv.smartsense.ui','com.vt.tv.smartservice',
    'com.vt.tv.input','com.vt.source.external','com.vt.source.tuner','com.vt.tv.tvcenter','com.vt.tvservice',
    'com.vt.tv.commonui','com.vt.avmiddleware','com.vt.edv.drmp','com.dolby.android.audio.service',
    'com.vt.tv.ota','com.vt.tv.usbota','com.vt.remoteupgrade','com.mediatek.autopair',
    'com.vt.tv.mobiledeviceconnectiontips','com.vt.tv.dlna','com.mediatek.partner.airplay_sys',
    'com.mediatek.AirplayAPK','com.mediatek.airplaydaemon','com.vt.tv.airplaykeycheck',
    'com.vt.tv.mediacenter','com.vt.tv.singlelisten',
}

def shell(*args):
    result=subprocess.run([str(ADB),'-s',SERIAL,'shell',*args],capture_output=True,text=True,timeout=25)
    if result.returncode:raise RuntimeError('TV command failed: '+' '.join(args[:3]))
    return result.stdout.strip()

def packages(flag=None):
    args=['pm','list','packages']+([flag] if flag else [])
    return {line.removeprefix('package:') for line in shell(*args).splitlines()}

def state(package):
    output=shell('dumpsys','package',package)
    match=re.search(r'User 0:.*?enabled=(\d+)',output)
    if not match:raise RuntimeError('Cannot resolve original package state: '+package)
    return int(match[1])

def save(path,value):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,indent=2)+'\n');temporary.chmod(0o600);os.replace(temporary,path)

def check_protected():
    enabled=packages('-e');installed=packages()
    missing=sorted((PROTECTED&installed)-enabled)
    if missing:raise RuntimeError('A protected package is not enabled: '+', '.join(missing))
    if shell('settings','get','secure','always_on_vpn_app')!='com.tailscale.ipn':
        raise RuntimeError('Tailscale automatic startup preference changed')

def prepare(directory):
    if shell('getprop','ro.product.device')!='lushan' or shell('getprop','ro.product.manufacturer')!='Hisense':
        raise RuntimeError('The connected TV is not the inspected Hisense lushan')
    check_protected()
    installed=packages();selected={p:reason for entries in STAGES.values() for p,reason in entries.items() if p in installed}
    if PROTECTED&selected.keys():raise RuntimeError('Protected package in disable plan')
    directory.mkdir(parents=True,exist_ok=True)
    plan_path=directory/'disable-plan.json'
    if plan_path.exists():return
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        states=dict(zip(selected,pool.map(state,selected)))
    plan={'device':SERIAL,'created_at':datetime.now().astimezone().isoformat(),
          'keep_features':['Google Assistant','casting/AirPlay','antenna/live TV'],
          'packages':{p:{'reason':reason,'original_state':states[p]} for p,reason in selected.items()}}
    save(plan_path,plan)
    save(directory/'applied.json',{'events':[]})
    print('Prepared disable plan:',len(selected),'packages',flush=True)

def apply(directory,stage):
    plan=json.loads((directory/'disable-plan.json').read_text());history_path=directory/'applied.json'
    history=json.loads(history_path.read_text())
    check_protected()
    for package in STAGES[stage]:
        if package not in plan['packages']:continue
        if package in PROTECTED:raise RuntimeError('Protected package blocked')
        if state(package) in (2,3,4):
            print('Already disabled:',package,flush=True);continue
        if package=='com.vt.fte' and (shell('settings','get','global','device_provisioned')!='1' or shell('settings','get','secure','user_setup_complete')!='1'):
            print('Preserved first-time setup because provisioning is incomplete.',flush=True);continue
        event={'package':package,'stage':stage,'at':datetime.now().astimezone().isoformat(),'status':'pending'}
        history['events'].append(event);save(history_path,history)
        result=shell('pm','disable-user','--user','0',package)
        if state(package)!=3:raise RuntimeError('Package did not enter disabled-user state: '+package)
        event.update(status='disabled',result=result);save(history_path,history)
        print('Disabled:',package,'('+STAGES[stage][package]+')',flush=True)
    check_protected()
    print('Protected package check passed.',flush=True)

def restore(directory):
    plan=json.loads((directory/'disable-plan.json').read_text())
    history=json.loads((directory/'applied.json').read_text())
    changed=list(dict.fromkeys(event['package'] for event in history['events']))
    for package in reversed(changed):
        original=plan['packages'][package]['original_state']
        command={0:'default-state',1:'enable',2:'disable',3:'disable-user',4:'disable-until-used'}.get(original)
        if command is None:raise RuntimeError('Unknown recorded state')
        shell('pm',command,'--user','0',package)
        if state(package)!=original:raise RuntimeError('Restoration check failed: '+package)
        print('Restored original state:',package,flush=True)
    save(directory/'restored.json',{'at':datetime.now().astimezone().isoformat(),'packages':changed})
    if 'dev.tvlivedashboard' in packages('-e'):
        shell('am','start','-n','dev.tvlivedashboard/.MainActivity','-f','0x10008000')
        print('Jarvis app menu refreshed.',flush=True)

if __name__=='__main__':
    os.umask(0o077)
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['prepare','apps','extras','restore'])
    parser.add_argument('snapshot',type=Path)
    args=parser.parse_args();directory=args.snapshot.resolve()
    if not directory.is_relative_to(ROOT/'state/debloat'):raise SystemExit('Use a project-owned debloat snapshot directory')
    if args.action=='prepare':prepare(directory)
    elif args.action=='restore':restore(directory)
    else:apply(directory,args.action)
