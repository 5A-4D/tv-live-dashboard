#!/usr/bin/env python3
"""Render and check the actual dashboard using fictional, network-isolated fixtures."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from serve import demo_server

ROOT = Path(__file__).resolve().parents[1]


def capture(output, executable=None):
    with demo_server() as origin, sync_playwright() as playwright:
        options = {'headless': True}
        if executable:
            options['executable_path'] = executable
        browser = playwright.chromium.launch(**options)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
        errors, blocked = [], []

        def allow_local(route):
            url = route.request.url
            if urlsplit(url).netloc == urlsplit(origin).netloc or url.startswith('data:'):
                route.continue_()
            else:
                blocked.append(urlsplit(url).hostname)
                route.abort()

        context.route('**/*', allow_local)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            page.goto(origin + '/demo/', wait_until='networkidle')
            page.wait_for_function("document.getElementById('reminderCount').textContent === '4'")
            assert not errors, errors
            assert not blocked, 'The demo attempted a non-local request'
            assert page.locator('.brand').inner_text().find('FICTIONAL') >= 0
            assert 'Riley' in page.locator('#greeting').inner_text()
            assert page.locator('.reminder-row').count() == 4
            assert page.locator('.headline').count() == 4
            assert page.locator('.usage-window').count() == 2
            assert page.evaluate('document.documentElement.scrollHeight <= innerHeight && document.documentElement.scrollWidth <= innerWidth')
            page.locator('#workButton').click()
            assert page.locator('.work-day').count() == 7
            page.evaluate("window.jarvisKey('back')")
            page.locator('#remindersButton').click()
            assert 'Review the project roadmap' in page.locator('.reminder-file').inner_text()
            page.evaluate("window.jarvisKey('back'); document.getElementById('firstApp').focus(); window.jarvisKey('right')")
            assert page.evaluate("document.activeElement.dataset.package === 'com.google.android.youtube.tv'")
            page.evaluate("window.jarvisKey('ok')")
            assert page.evaluate("window.TV_DEMO_LAST_ACTION === 'com.google.android.youtube.tv'")
            page.evaluate('window.receiveNetworkError()')
            assert page.locator('#linkBadge').inner_text() == 'Showing saved data'
            assert page.locator('#clockTime').inner_text() != '--:--'
            page.evaluate('window.TV_DEMO.publish()')
            assert page.locator('#linkBadge').inner_text() == 'Home server connected'
            page.evaluate('document.activeElement.blur()')
            page.wait_for_timeout(500)
            assert not errors, errors
            assert not blocked, 'The demo attempted a non-local request'
            output.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(output), full_page=False, animations='disabled')
            result = {'viewport': '1920x1080', 'fictional_data_only': True,
                      'external_requests': len(blocked), 'javascript_errors': len(errors),
                      'checks': ['layout', 'widgets', 'week view', 'reminder details',
                                 'remote navigation', 'app bridge', 'offline cache', 'recovery'],
                      'screenshot': str(output.relative_to(ROOT))}
            print(json.dumps(result))
            return result
        finally:
            context.close()
            browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chromium', help='Optional installed Chromium/Chrome executable')
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/images/demo-dashboard.png')
    args = parser.parse_args()
    capture(args.output.resolve(), args.chromium)
