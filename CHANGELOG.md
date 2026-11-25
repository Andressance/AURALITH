# Changelog

All notable changes to Auralith are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

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
