"""Exercise real app launching, Home override and API outage recovery on the target TV."""
import subprocess
import time
from tv_smoke import ADB, Browser, SERIAL

def shell(*args):
    return subprocess.run([str(ADB),'-s',SERIAL,'shell',*args],capture_output=True,text=True,check=True,timeout=20).stdout

def wait_foreground(package):
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        output=shell('dumpsys','activity','activities')
        resumed=[line for line in output.splitlines() if 'mResumedActivity' in line]
        if any(package+'/' in line for line in resumed):return
        time.sleep(.25)
    raise AssertionError('Expected foreground app: '+package)

def connect():
    pid=shell('pidof','dev.tvlivedashboard').strip().split()[0]
    subprocess.run([str(ADB),'-s',SERIAL,'forward','tcp:9223','localabstract:webview_devtools_remote_'+pid],check=True,capture_output=True)
    return Browser()

if __name__=='__main__':
    browser=connect()
    stopped=False
    try:
        browser.evaluate("window.jarvisKey('back');document.getElementById('firstApp').focus()")
        shell('input','keyevent','KEYCODE_DPAD_RIGHT')
        shell('input','keyevent','KEYCODE_DPAD_CENTER')
        wait_foreground('com.google.android.youtube.tv')
        shell('input','keyevent','KEYCODE_HOME')
        wait_foreground('dev.tvlivedashboard')
        browser.close();browser=connect()
        browser.wait("document.getElementById('linkBadge').innerText==='Home server connected'")
        print('PASS: YouTube shortcut and return Home to Jarvis')

        subprocess.run(['docker','stop','--time','3','tv-live-dashboard'],check=True,capture_output=True)
        stopped=True
        browser.evaluate('JarvisNative.refresh()')
        browser.wait("document.getElementById('linkBadge').innerText==='Showing saved data'")
        assert browser.evaluate("document.getElementById('clockTime').innerText!=='--:--'")
        browser.evaluate("document.getElementById('firstApp').focus()")
        shell('input','keyevent','KEYCODE_DPAD_CENTER')
        wait_foreground('org.jellyfin.androidtv')
        shell('input','keyevent','KEYCODE_HOME')
        wait_foreground('dev.tvlivedashboard')
        browser.close();browser=connect()
        browser.wait("document.getElementById('linkBadge').innerText==='Showing saved data'")
        print('PASS: offline clock, cached data, Jellyfin shortcut and Home override')
    finally:
        if stopped:subprocess.run(['docker','start','tv-live-dashboard'],check=True,capture_output=True)
        browser.close()
    browser=connect()
    try:
        # Wait for API readiness, then allow an in-flight failed request to settle.
        from urllib.request import urlopen
        deadline=time.monotonic()+12
        while time.monotonic()<deadline:
            try:
                urlopen('http://192.0.2.10:8768/healthz',timeout=1).close()
                break
            except OSError:time.sleep(.2)
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            browser.evaluate('JarvisNative.refresh()')
            if browser.evaluate("document.getElementById('linkBadge').innerText==='Home server connected'"):break
            time.sleep(.5)
        else:raise AssertionError('Dashboard did not recover after API readiness')
        print('PASS: live dashboard automatically recovers after the service returns')
    finally:browser.close()
