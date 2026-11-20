# Portfolio snapshot

Prepared November 20, 2026 as a private, one-time publication of an existing
Android TV launcher/dashboard. Its portfolio title is TV Live Dashboard.

## Preparation

- Generalized display branding, application package, device addresses, local
  account paths, personal names and location settings.
- Added a fictional browser demo and screenshot using the actual UI.
- Restricted the demo asset server to static demo/web content.
- Rewrote operational notes without the private deployment record.

The original source, installed TV, signing key and services were not modified or
restarted. This repository is not an ongoing development remote.

## Exclusions

Original `state/` and `build/`, API credentials, pairing capabilities, Android
signing material, actual reminders/calendar/status feeds, hardware captures and
recovery journals are excluded. Fresh example signing material used for build
validation also remains uncommitted. Generated APKs are not uploaded.

## Validation

- All 30 standard-library regression tests passed in an isolated container.
- The actual dashboard rendered at 1920 × 1080 with fictional fixtures. Browser
  checks passed for layout, widgets, week/reminder overlays, remote navigation,
  app bridge, offline cache and reconnection, with no external page requests or
  JavaScript errors.
- The renamed Android app compiled successfully. Its fresh example APK passed
  Android signature verification (v2/v3); the APK and example signing state were
  removed after verification.
- Publication files were checked against private deployment values and scanned
  for secrets. The new Git history is scanned again before upload.

These checks cannot guarantee detection of every possible sensitive value.

Deprecated Android APIs are retained from the working prototype. Browser tests
do not establish launcher/Home or cleanup behavior on another TV model; that
requires separate hardware validation.
