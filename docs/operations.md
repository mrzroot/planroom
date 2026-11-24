# Linux staging runbook

Use a separate checkout and a distinct Compose project for staging. Use only fictional data and restrict access to reviewers. The Compose application binds to loopback. The API and PostgreSQL stay on the Compose network.

1. Copy `.env.example` to `.env`, set a unique `POSTGRES_PASSWORD`, and set `APP_ORIGIN` to the exact external HTTPS origin with no trailing slash, such as `https://staging.example.org`. Keep the file out of Git and restrict its permissions with `chmod 600 .env`.
2. Configure the host's HTTPS reverse proxy to forward the staging hostname to `127.0.0.1:8088` or the configured `APP_PORT`. Keep reviewer access controls at that proxy. This also enables the application's Secure session cookie. The Compose proxy rate-limits auth on the IP it sees, so visitors sharing the upstream proxy share a rate limit.
3. Run `docker compose -p planroom-staging up -d --build --wait`. The API applies Alembic migrations before reporting ready. Run one API container per stack because migrations run at API startup.
4. Visit the staging URL and start a sample workspace. Confirm readiness with `curl -fsS "$STAGING_URL/api/health/ready"`. Point an uptime check at that endpoint from inside the trusted network. Liveness is at `/api/health/live`. Inspect access logs and application errors with `docker compose -p planroom-staging logs --tail 100 web api db`.

## Backup and restore drill

Run these Bash commands from the staging checkout. Keep backups in access-controlled storage outside the checkout. The temporary file prevents an incomplete dump from replacing a usable backup.

```bash
set -euo pipefail
umask 077
mkdir -p "$HOME/planroom-backups"
backup="$HOME/planroom-backups/planroom-$(date -u +%Y%m%dT%H%M%SZ).dump"
docker compose -p planroom-staging exec -T db pg_dump -U planroom -Fc planroom > "$backup.part"
mv -- "$backup.part" "$backup"

# Use a fresh, uniquely named database for each drill.
restore_db="planroom_restore_$(date -u +%Y%m%d%H%M%S)"
docker compose -p planroom-staging exec -T db createdb -U planroom "$restore_db"
docker compose -p planroom-staging exec -T db pg_restore -U planroom --exit-on-error --single-transaction -d "$restore_db" < "$backup"
docker compose -p planroom-staging exec -T db psql -U planroom -d "$restore_db" -v ON_ERROR_STOP=1 \
  -c 'SELECT version_num FROM alembic_version;' -c 'SELECT count(*) FROM accounts;'
```

Schedule the dump on the staging host and alert on failed runs. Verify a restored account count against the source and record the drill result. Treat dumps as credentials because they include account and session data. After a verified drill, have the staging operator remove that drill database by its exact name.

## Updating staging

Record the running Git SHA and take a backup before applying a new revision. Deploy the chosen commit with the same Compose command, then check readiness and the sample flow. For rollback, check migration compatibility before restarting an older image. If recovery requires restoring a backup, restore to a fresh database, invalidate restored sessions, check the data, and switch in a maintenance window.
