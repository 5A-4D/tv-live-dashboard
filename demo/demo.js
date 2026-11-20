/* Fictional offline fixtures. This file never calls an API or reads a local feed. */
(function () {
  'use strict';
  var RealDate = window.Date;
  var instant = RealDate.parse('2026-01-14T14:42:00Z');
  window.Date = class extends RealDate {
    constructor() {
      var args = Array.prototype.slice.call(arguments);
      super(...(args.length ? args : [instant]));
    }
    static now() { return instant; }
  };
  var now = instant / 1000;
  window.JARVIS_CONFIG = Object.freeze(Object.assign({}, window.JARVIS_CONFIG, {
    name: 'Riley', timezone: 'UTC', defaultTheme: 'winter',
    daylight: {enabled: true, latitude: 51.4769, longitude: 0},
    ambientAfterSeconds: 86400
  }));
  localStorage.setItem('jarvis-dim', 'off');
  localStorage.setItem('jarvis-theme', 'winter');
  var items = [
    {text: '1. Review the project roadmap', priority: 1, done: false},
    {text: '2. Plan a weekend movie night', priority: 2, done: false},
    {text: '3. Water the plants', priority: 3, done: false},
    {text: '4. Read tomorrow’s briefing', priority: 4, done: false}
  ];
  var days = [];
  for (var index = 0; index < 7; index++) {
    var date = new RealDate(RealDate.UTC(2026, 0, 12 + index));
    var start = date.getTime() / 1000 + 9 * 3600;
    days.push({date: date.toISOString().slice(0, 10), working: index < 5,
      start: start, end: start + 8 * 3600,
      busy: index < 5 ? [{start: start, end: start + 3600},
                        {start: start + 6 * 3600, end: start + 6.5 * 3600}] : []});
  }
  var snapshot = {
    schema: 1, demo: true, collected_at: now, served_at: now, feed_stale: false,
    reminders: {available: true, unfinished: 4, completed: 0, items: items,
      raw: items.map(function (item) { return '[ ] ' + item.text; }).join('\n')},
    services: [
      {id: 'jarvis-discord', label: 'Jarvis', online: true, stale: false, state: 'running', uptime_seconds: 187200},
      {id: 'jellyfin', label: 'Jellyfin', online: true, stale: false, state: 'running', uptime_seconds: 446400}
    ],
    jarvis: {ready: true, activity: {state: 'idle', active_count: 0, last_success_at: now - 180}},
    host: {uptime_seconds: 619200, storage: [{label: 'Media', used_percent: 42}]},
    work: {available: true, checked_at: now, timezone: 'UTC', days: days},
    codex: {available: true, checked_at: now, windows: [
      {used_percent: 31, window_minutes: 300, resets_at: now + 7920},
      {used_percent: 18, window_minutes: 10080, resets_at: now + 259200}
    ]},
    weather: {available: true, checked_at: now, observed_at: now - 60, location: 'Lakeview · Demo',
      temperature: 42, feels_like: 39, high: 46, low: 29, code: 2, rain_chance: 15, wind_mph: 8, unit: '°F'},
    news: {checked_at: now, items: [
      {source: 'DEMO JOURNAL', title: 'A quieter home screen, designed around your day'},
      {source: 'TECH BRIEF · DEMO', title: 'Small local tools make everyday routines simpler'},
      {source: 'COMMUNITY NOTES · DEMO', title: 'Neighborhood library announces a winter reading series'},
      {source: 'WEEKEND EDIT · DEMO', title: 'Make room for a movie night and a little downtime'}
    ]},
    teams: {configured: true, initialized: true, pending: false, last_received_at: now - 3600},
    alerts: [], outages: {available: true, checked_at: now, items: [], unavailable_sources: []}
  };
  var apps = [
    {package: 'org.jellyfin.androidtv', label: 'Jellyfin'},
    {package: 'com.google.android.youtube.tv', label: 'YouTube'},
    {package: 'com.tailscale.ipn', label: 'Tailscale'},
    {package: 'demo.settings', label: 'TV settings'}
  ];
  function publish() {
    window.receiveApps(JSON.stringify(apps));
    window.receiveSnapshot(JSON.stringify(snapshot), true);
    document.querySelector('.brand strong').textContent = 'TV LIVE';
    document.querySelector('.brand div > span').textContent = 'DEMO · ALL INFORMATION IS FICTIONAL';
    document.querySelector('.weather-credit').textContent = 'Demo weather · fictional';
  }
  function demoAction(action) { window.TV_DEMO_LAST_ACTION = action; }
  window.JarvisNative = {
    ready: publish, refresh: publish,
    launch: function (pkg) { demoAction(pkg); },
    settings: function () { demoAction('settings'); },
    accessibility: function () { demoAction('accessibility'); }
  };
  window.TV_DEMO = {snapshot: snapshot, publish: publish, fixedTime: instant};
}());
