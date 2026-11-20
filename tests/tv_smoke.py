"""On-TV UI checks; requires a temporary WebView debug connection on localhost:9223."""
import hashlib
import json
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen
import websocket

ROOT = Path(__file__).resolve().parents[1]
ADB = Path.home() / '.local/share/google-android-tools/platform-tools/adb'
SERIAL = '192.0.2.20:5555'

class Browser:
    def __init__(self):
        pages = json.load(urlopen('http://127.0.0.1:9223/json', timeout=5))
        page = next(p for p in pages if p.get('type') == 'page' and p.get('url','').startswith('https://jarvis.local/'))
        self.ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=8, suppress_origin=True)
        self.ident = 0

    def evaluate(self, expression):
        self.ident += 1
        self.ws.send(json.dumps({'id':self.ident,'method':'Runtime.evaluate','params':{'expression':expression,'returnByValue':True,'awaitPromise':True}}))
        while True:
            message = json.loads(self.ws.recv())
            if message.get('id') == self.ident:
                result = message['result']
                if 'exceptionDetails' in result:
                    raise AssertionError('JavaScript exception during UI check')
                return result['result'].get('value')

    def wait(self, expression, timeout=8):
        deadline = time.monotonic()+timeout
        while time.monotonic()<deadline:
            if self.evaluate(expression):
                return
            time.sleep(.15)
        raise AssertionError('UI condition did not become true: '+expression)

    def close(self):
        self.ws.close()

if __name__ == '__main__':
    browser = Browser()
    try:
        browser.wait("document.getElementById('linkBadge').innerText === 'Home server connected'")
        assert browser.evaluate("typeof window.jarvisKey==='function' && document.getElementById('clockTime').innerText!=='--:--'")
        assert browser.evaluate("document.documentElement.scrollHeight <= innerHeight && document.documentElement.scrollWidth <= innerWidth")
        assert browser.evaluate("document.querySelectorAll('.headline').length===4")
        assert browser.evaluate("document.querySelectorAll('.usage-window').length>=1")
        browser.evaluate("document.getElementById('workButton').click()")
        assert browser.evaluate("document.querySelectorAll('.work-day').length===7")
        browser.evaluate("window.jarvisKey('back')")
        browser.evaluate("document.getElementById('allAppsButton').click()")
        assert browser.evaluate("document.querySelectorAll('.installed-app').length >= 3")
        browser.evaluate("window.jarvisKey('back');document.getElementById('remindersButton').click()")
        actual = browser.evaluate("crypto.subtle.digest('SHA-256',new TextEncoder().encode(document.querySelector('.reminder-file').textContent)).then(b=>Array.from(new Uint8Array(b)).map(x=>x.toString(16).padStart(2,'0')).join(''))")
        expected = hashlib.sha256(Path('/home/your-user/Desktop/reminder.txt').read_text().encode()).hexdigest()
        assert actual == expected, 'Full reminder display differs from source'
        browser.evaluate("window.jarvisKey('back');document.getElementById('firstApp').focus()")
        subprocess.run([str(ADB),'-s',SERIAL,'shell','input','keyevent','KEYCODE_DPAD_RIGHT'],check=True,capture_output=True)
        browser.wait("document.activeElement.getAttribute('data-package')==='com.google.android.youtube.tv'")
        browser.evaluate("document.getElementById('firstApp').focus()")
        print('PASS: live data, clock, screen bounds, news, Codex usage, work week, all apps, verbatim reminders, D-pad navigation')
    finally:
        browser.close()
