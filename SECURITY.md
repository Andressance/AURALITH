# Security

Auralith is under active development. Report vulnerabilities privately to the repository maintainer instead of opening a public issue.

## MVP controls currently implemented

- Argon2id password hashing and strong owner-password validation at startup.
- Twelve-hour sessions with HTTP-only cookies; the frontend also uses a bearer token for cross-origin API/media requests.
- Login throttling (5 attempts per 15 minutes per client address) and an API-wide limit (300 requests per minute per address).
- In-memory rate-limit state with bounded key counts. Limits apply per API process and are not DDoS protection.
- Forwarded client addresses are used only when the immediate peer belongs to `AURALITH_TRUSTED_PROXIES`; otherwise the socket peer is used.
- Exact CORS origin allowlist by default. `AURALITH_ALLOW_VERCEL_ORIGINS=true` opts into any Vercel subdomain and should be avoided for production.
- Origin checks for mutations, a Fetch Metadata check for cross-site mutations without an Origin header, and security response headers.
- MP3/FLAC extension and signature checks, SHA-256 deduplication, bounded metadata fields, and a 100 MB audio-file limit.
- Artwork processing has size/dimension limits and a single processing slot.
- CSV import is limited to 2 MB and 500 rows; only exact matches are added automatically. Approximate/ambiguous matches require confirmation.
- HTTP Range validation for audio streaming.
- ZIP restore validates member paths and caps uncompressed size at 1 GB.
- Supabase Storage buckets are private, public REST access is revoked by RLS, and storage URLs are not used as public redirects.

## Account and library access

The music catalog is shared within an Auralith instance: authenticated guest accounts can play visible catalog tracks, while playlists, favorites, and hidden-track preferences are account-specific. Only the owner can manage accounts and permanently delete catalog tracks. Private object storage is never exposed directly; API routes authorize access before serving media.

## Deployment requirements

- Set a strong `AURALITH_OWNER_PASSWORD`.
- Serve the app over HTTPS and keep `AURALITH_COOKIE_SECURE=true`.
- Set `AURALITH_CORS_ORIGINS` to exact frontend origins. Keep `AURALITH_ALLOW_VERCEL_ORIGINS` unset or `false` in production.
- If deployed behind a reverse proxy, set `AURALITH_TRUSTED_PROXIES` to that proxy's exact IPs/CIDRs. Only configure proxies that sanitize/append `X-Forwarded-For`; never trust arbitrary client-supplied forwarding headers.
- Redact query strings from access logs: browser media URLs currently include a session bearer token for cross-origin playback and artwork.
- Never expose `SUPABASE_SECRET_KEY`, deprecated `SUPABASE_SERVICE_ROLE_KEY`, or cloud-storage credentials to frontend code.
- Use a TLS reverse proxy or platform HTTPS endpoint. Put volumetric DDoS protection and edge-level request limits at the hosting provider/CDN; the in-process limiter cannot absorb network floods and is not shared across replicas.
- Back up the database and music storage.

## Known limitations before public release

- Login and API rate limits are process-local. Multi-worker or multi-replica deployments need a shared limiter or equivalent edge policy.
- Audio metadata parsing still runs in the API process. Heavy antivirus scanning, sandboxing, transcoding, and a dedicated bounded job queue are not MVP requirements and are not implemented.
- Media URLs currently use the session token in the query string to support browser audio/image elements across origins. Logs must redact query strings; replacing this with short-lived media-scoped URLs remains a hardening item.
- The application-level limits cannot replace provider-level DDoS protection or reverse-proxy body-size limits.
- No antivirus scan is performed. Format checks and streaming do not prove that media is harmless.
- Federation, remote-media authorization, Google Drive/Dropbox archival storage, and automatic media replication are not implemented.

## Dependency and release verification

Run before release:

```bash
python -m pytest -p no:asyncio -q
python -m pip_audit
python -m pip check
cd apps/web && npm audit --omit=dev && npm run build
docker compose config
```
