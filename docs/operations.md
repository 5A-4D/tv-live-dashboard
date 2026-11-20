# Operations and configuration reference

The browser demo needs no services or credentials. The native launcher/live
widgets require a configured TV and backend. Addresses and paths here are examples.

## Data path

Host collectors write selected JSON into `state/feed/`. The API reads that feed
and a private credential. The native app requests a fixed dashboard endpoint,
caches the selected snapshot, and passes it into the bundled interface.
API access requires both the configured source allowlist and dashboard key.
The optional phone receiver has a separate key/source allowlist and accepts only
fixed `received`/`clear` events, with no notification text.

Compose defaults to loopback until an address is configured. Host networking
preserves client addresses. The API container uses a read-only root, dropped
capabilities and bounded resources. Selected feed/key mounts are read-only;
phone-signal state is writable.

## Collectors

- `collect_feed.py`: selected reminders, service/heartbeat status, and content-free
  activity/timestamps. Adapt its source paths and service names.
- `collect_codex.py`: selected supported usage windows; no account/authentication fields.
- `collect_work.py`: the separately configured Jarvis calendar reader, exporting
  anonymous intervals. Pass configured series exclusions explicitly; unrelated
  overlapping events must still block their own intervals.
- `install_feed_timer.py`: host timer templates requiring path/command review.

The companion Jarvis reader is not vendored. Calendar/usage collection requires
its separately configured runtime. The fictional demo needs neither integration.

## Android and targets

`init_example_config.py` creates fresh example state for build verification.
For live use, configure the endpoint pin in `MainActivity.java`, network-security
resource, API/source allowlists, and device targets in the deployment references.
Keep a stable private signing key for app updates; this snapshot's fresh example
signer cannot update an existing app signed with a different key.
No hardware-targeting script runs during normal unit/browser tests or publication.

## Cleanup and recovery

`debloat_tv.py` records original package states, applies a reviewed disable plan,
and verifies protected functionality. Restoration replays recorded states.
APKs/data are retained; this is reversible package disabling on Android firmware.

The plan is specific to the reviewed Hisense `lushan` board. Keep networking,
input, display/audio, store, updates, Assistant, casting, live TV and recovery
launchers available. A matching board does not establish that every package
choice suits another owner.

Home/VPN recovery helpers and hardware checks retain operational references.
Their real-device journals belong in ignored `state/`/`build/`, not this repository.
