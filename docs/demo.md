# Fictional dashboard demonstration

The README screenshot is an actual Chromium render of the dashboard, using the
same stylesheet, widgets, animation and renderer as the Android app.

`demo/demo.js` provides a native-bridge substitute and invented fixtures, fixing
the clock at January 14, 2026, 14:42 UTC. Riley and Lakeview are demonstration
labels. Every reminder, interval, headline, usage value, phone/service status and
weather value is fictional. No credentials are needed or real collectors started.

Install `requirements-demo.txt` and a Chromium browser, then run:

```sh
python demo/capture.py
```

The output is `docs/images/demo-dashboard.png` at 1920×1080. The script starts a
restricted loopback asset server and fresh browser context, blocks non-local
page requests, verifies widgets/navigation/offline behavior, takes a screenshot,
and closes the browser/server. App launches are simulated and recorded in memory.

Android bundles `web/`, not `demo/`. Screenshot fixtures cannot become a real
calendar or production feed through the APK build process.
