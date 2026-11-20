#!/usr/bin/env python3
"""Read account limits through Codex's existing local app-server; never start an inference turn."""
import json
import os
from pathlib import Path
import select
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
CODEX=Path.home()/'.local/bin/codex'

class RPC:
    def __init__(self):
        self.process=subprocess.Popen([str(CODEX),'app-server','--listen','stdio://'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        self.buffer=b''
        self.ident=0
    def send(self,message):
        self.process.stdin.write((json.dumps(message)+'\n').encode());self.process.stdin.flush()
    def request(self,method,params=None):
        self.ident+=1
        message={'id':self.ident,'method':method}
        if params is not None:message['params']=params
        self.send(message)
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            while b'\n' in self.buffer:
                line,self.buffer=self.buffer.split(b'\n',1)
                try:value=json.loads(line)
                except ValueError:continue
                if value.get('id')==self.ident:
                    if 'error' in value:raise RuntimeError('Usage data is unavailable')
                    return value.get('result',{})
            ready,_,_=select.select([self.process.stdout],[],[],max(0,deadline-time.monotonic()))
            if ready:
                chunk=os.read(self.process.stdout.fileno(),65536)
                if not chunk:raise RuntimeError('Usage connection closed')
                self.buffer+=chunk
                if len(self.buffer)>2_000_000:raise RuntimeError('Usage response too large')
        raise TimeoutError('Usage request timed out')
    def close(self):
        self.process.terminate()
        try:self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:self.process.kill();self.process.wait()

def select_limits(result):
    buckets=result.get('rateLimitsByLimitId') or {}
    rate=buckets.get('codex') or result.get('rateLimits') or {}
    windows=[]
    for key in ('primary','secondary'):
        value=rate.get(key)
        if not isinstance(value,dict):continue
        percent=value.get('usedPercent');minutes=value.get('windowDurationMins');reset=value.get('resetsAt')
        if not isinstance(percent,(int,float)) or not isinstance(minutes,(int,float)):continue
        windows.append({'used_percent':max(0,min(100,percent)), 'window_minutes':minutes,
                        'resets_at':reset if isinstance(reset,(int,float)) else None})
    return windows

def collect():
    client=RPC()
    try:
        client.request('initialize',{'clientInfo':{'name':'jarvis_home_usage','title':'TV Live Dashboard usage display','version':'0.1.0'}})
        client.send({'method':'initialized'})
        result=client.request('account/rateLimits/read')
        windows=select_limits(result)
        return {'available':bool(windows),'checked_at':time.time(),'windows':windows}
    finally:client.close()

if __name__=='__main__':
    os.umask(0o077)
    try:result=collect()
    except Exception:result={'available':False,'checked_at':None,'windows':[]}
    path=ROOT/'state/feed/codex.json';temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(result,allow_nan=False)+'\n');temporary.chmod(0o600);os.replace(temporary,path)
    print('Codex usage:', 'updated' if result['available'] else 'unavailable')
