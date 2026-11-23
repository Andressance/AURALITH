# Security

Auralith is under active development. Report vulnerabilities privately to the repository maintainer instead of opening a public issue.

## MVP security controls

- Argon2id password hashing.
- Strong owner-password startup validation.
- HTTP-only, SameSite session cookies.
- Secure cookies by default in production.
- Twelve-hour session expiry.
- Login rate limiting.
- Origin and Fetch Metadata checks for mutations.
- Security response headers.
- Disabled API documentation outside development.
- Private library and storage authorization by owner ID.
- MP3/FLAC signature validation and Mutagen parsing.
- 100 MB upload limit.
- Sanitized metadata and playlist names.
- HTTP Range validation.
- Private Supabase Storage bucket.
- Supabase RLS enabled with public REST access revoked.
- Supabase Storage service URLs blocked from redirects.
- Backup decompression limits and ZIP path traversal checks.
- No public API documentation or public storage policy in production.

## Deployment requirements

- Set a strong `AURALITH_OWNER_PASSWORD`.
- Set `AURALITH_COOKIE_SECURE=true` behind HTTPS.
- Set `AURALITH_CORS_ORIGINS` to exact frontend origins.
- Never expose `SUPABASE_SERVICE_ROLE_KEY` to frontend code.
- Use a TLS reverse proxy or platform HTTPS endpoint.
- Keep the Docker volume or database and music storage backed up.

## Dependency verification

Run before release:

```bash
pytest -q
python3 -m pip_audit
python3 -m pip check
cd apps/web && npm audit --omit=dev && npm run build
docker compose config
```
