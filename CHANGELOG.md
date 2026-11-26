# Changelog

All notable changes to Auralith are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

## [Unreleased]

### Added

- Full-screen now-playing view in the style of a streaming app: large artwork, scrubable
  progress with elapsed and remaining time, transport controls, favorites, volume and a
  shortcut to the artist. It opens from the mini player and closes by pulling it down.
- Grouped search: artists, albums and songs in one result page, with instant filtering of
  the library instead of a flat track list.
- Artist page built from library metadata: popular songs by local play count, albums that
  expand into their track list, and every song of the artist.
- Listening statistics per account: each playback session is stored with its listened
  seconds and date, so minutes are real playback time and not the length of the file.
- "Wrapped": a yearly summary with total minutes, top artists and their minutes, most
  played song and albums, and a month-by-month chart, reachable from the sidebar and at
  `/wrapped`.
- Editable statistics dashboard at `/stats`: period switch (year, month, all time),
  totals, and widgets that can be added, renamed, reordered and removed. Chart types are
  bars, columns, donut, ranked list and a big number, over hours of the day, weekdays,
  months, artists, songs, albums and genres, by minutes or plays.
- `GET /api/stats/overview` exposes those breakdowns; the dashboard layout is stored per
  account in `stats_dashboards` and defaults are restored with one click.
- The listening history can be exported as CSV and trimmed from the profile page: older
  than 90 days, older than a year, or everything. `GET /api/stats/plays/export` and
  `DELETE /api/stats/plays` back those buttons.

### Fixed

- Selecting a playlist while a search was active kept showing the search results; the
  playlist now opens and the search is cleared.

### Notes

- Listening statistics start with the first playback after this release; past plays are
  not reconstructed.

## [1.3.0] — 2026-11-25

### Added

- Devices: signed-in browsers of one account see each other. Only one device plays at a
  time, and a device can control another one or take over its playback.
- Media Session controls (play, pause, previous, next, seek) with playback state and
  position, so Windows shows them for an installed app.
- Browser test of the jam flow in `tests/e2e`, skipped unless its environment is set.

### Changed

- The web frontend is split into components (`apps/web/src/components`) with no change in behaviour.
- Jams broadcast the full state after every change, so the queue never drifts.
- Play buttons inside a jam set the jam's track for every member.
- The jam library lists the whole collection with search; tracks can be queued as next
  and the queue can be reordered.
- A track that ends advances the jam once, not once per member.

### Fixed

- Uploads failed on Windows: mutagen could not reopen the temporary file.
- Uploads of files without ID3 tags lost their duration.
- Library action buttons overlapped the selection checkbox.
- The desktop app opened no window on some machines: GPU acceleration is off, a second
  launch focuses the open window, and a crashed renderer reloads.
- The desktop app now uses its own icon in the window, the executable and the installer.

## [1.2.0] — 2026-11-25

### Added

- Jams: create a room, share its six-character code and listen to the same track at
  the same time with other accounts of the instance.
- Real-time state over WebSocket: playback changes, participants and queue updates
  reach every listener, with a REST snapshot for late joiners and page reloads.
- Anyone in the jam can play, pause, skip and queue tracks; the queue shows who added
  each track and the host can end the jam.
- The jam is remembered locally, so reloading the page rejoins it.

### Security

- A jam is invisible until you join it: reading, controlling and queueing all require
  membership, and sockets authenticate before receiving anything.
- The WebSocket handshake uses the session token; rooms are keyed by the jam code and
  a bad token closes the socket with 4401.

## [1.1.0] — 2026-11-25

### Added

- Two share levels for playlists: read-only and collaborative editing, switchable per
  person from the share panel.
- Collaborators can add and remove tracks of a shared playlist; the owner keeps the
  title, the cover and access management.
- Shared playlists can be kept in or removed from your library, and the library
  sidebar only lists the ones you saved.
- Playlist cards show the author and whether you collaborate on them.

## [1.0.0] — 2026-11-25

First stable release: a self-hosted personal music cloud for one owner and the
people they invite.

### Accounts and security

- Owner bootstrap with a strong-password policy and single-use invitations.
- Argon2 password hashes, HTTP-only session cookies and bearer tokens.
- Session rotation on password change, expiring sessions and login rate limiting.
- HMAC-signed media URLs so `<audio>` and `<img>` work without exposing the session token.
- Restricted CORS, real client IP behind trusted proxies, private per-user data.

### Library

- MP3 and FLAC uploads with header validation, Mutagen metadata and SHA-256 deduplication.
- Embedded artwork normalised to 512 px WebP, reusable as playlist covers.
- Instance-wide catalog with per-user hidden tracks, favorites and search.
- Playlists with ordering, custom covers and drag and drop.
- CSV playlist import with exact/approximate matching and a manual review report.
- Explicit, revocable playlist sharing between accounts of the same instance.

### Playback

- Range-based streaming with seek, signed URLs and cache headers.
- Queue, shuffle, repeat and Media Session (lock screen controls).
- Global persistent player and responsive layout for desktop and mobile.

### Storage and deployment

- Pluggable storage: local filesystem, Supabase Storage, any S3-compatible bucket
  and Google Drive (user OAuth, HTTP Range reads).
- Several backends at once: writes are replicated, reads fall back when one is
  unavailable, and `AURALITH_STORAGE_MIRROR=false` writes only to the first healthy
  provider.
- Alembic migrations applied on container start; a single Dockerfile supports both
  build contexts (repository root and `apps/api`).
- ZIP backup of SQLite plus local storage, with a consistent SQLite snapshot.
- Installable PWA with an offline app shell.
- CI runs pyflakes, the test suite and both Docker builds.

### Known limitations

- Playlist sharing is read-only with a single access level; per-library privacy and
  finer permissions are V1.5.
- Backup and restore require SQLite plus a single local storage provider.
- Google Drive is verified against a simulated API; a live account may reveal quota
  or permission differences.
- Federation, friends, statistics and downloads are out of scope for V1.
