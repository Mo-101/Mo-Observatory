# MoStar Sovereign Signal Observatory
Portable React dashboard, Python API, independent collector, SQLite evidence ledger and optional Caddy HTTPS gateway. No ChatGPT runtime is needed after deployment.

## Delivery status

The app is packaged for Git and a Linux VPS. It has NOT been deployed to your VPS. No working upstream feed has been verified or bundled. Configure a verified normalized SANSA JSON endpoint before collection can succeed. The old website and its upstream outage are not repaired by this archive alone.

There is no simulated production telemetry or hard-coded fallback. A new installation starts empty. Historic research cases remain clearly labeled review records; they are not telescope feeds or new detections. The board is read-only, without authenticated reviewer edits or automated scientific escalation. Source claims in those inherited records have not been independently reverified for this package.

## Architecture

The collector polls configured sources every 60 seconds, even with no browser open. Each response is hashed and retained; each attempt is recorded. Valid measurements are deduplicated by source, channel and observation time. Same-time disagreements are quarantined for scoring while both payloads remain available. The API reads persistent SQLite storage, and the frontend refreshes every 15 seconds.

Channel health comes from the measurement time, not retrieval time. Null stays null. Missing or stale channels pause dependent indices. The speed-energy index `(wind / 400)^2` and southward coupling index `(wind / 400) * max(0, -Bz)` are operational proxies, not energy in joules. Both require fresh values with identical timestamps. No physical cross-domain correlation is automatically asserted.

## Put it in Git

Extract this folder, then run inside it:

```bash
git init -b main
git add .
git commit -m "Package persistent observatory for VPS"
git remote add origin YOUR_GIT_REMOTE
git push -u origin main
```

Replace `YOUR_GIT_REMOTE` with your own repository URL. `.env`, databases, backups and dependency folders are excluded from Git. Keep credentials out of source URLs: attempt URLs are visible in the audit UI.

## VPS deployment path: /opt/mostar/observatory

Prerequisites: Linux VPS, Git, Docker Engine with Compose v2, and outbound HTTPS access to package registries and the configured source. Install Docker using the official instructions for your VPS distribution. Run these commands with an account authorized to use Docker and write `/opt/mostar`:

```bash
sudo mkdir -p /opt/mostar
sudo chown "$USER" /opt/mostar
git clone YOUR_GIT_REMOTE /opt/mostar/observatory
cd /opt/mostar/observatory
cp .env.example .env
chmod 600 .env
nano .env

docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs --tail=50 collector
curl http://127.0.0.1:8080/healthz
curl -i http://127.0.0.1:8080/readyz
```

Set `SOURCE_URLS` before starting. An empty value makes the collector exit with an explicit configuration error; the dashboard still opens and shows unavailable channels. `/healthz` indicates API/database liveness. `/readyz` deliberately returns 503 until all six channels are fresh, populated and conflict-free. A 200 API response alone never proves live telemetry.

Initially access it through an SSH tunnel from your computer:

```bash
ssh -L 8080:127.0.0.1:8080 YOUR_VPS_USER@YOUR_VPS_IP
```

Open http://localhost:8080. The API binds only to loopback on the VPS.

### Public HTTPS with authentication

Point your domain's DNS records to the VPS and allow inbound TCP ports 80/443. Generate a password hash interactively:

```bash
docker run --rm -it caddy:2-alpine caddy hash-password
```

Set `DOMAIN`, `BASIC_AUTH_USER` and `BASIC_AUTH_HASH` in `.env`. Put the hash in **single quotes**, preserving its dollar signs. Then:

```bash
docker compose --profile public up -d --build
docker compose logs --tail=50 proxy
```

Caddy provides certificates and protects the dashboard, API and raw evidence with the same login. Check the actual domain in a browser. Do not expose port 8080 directly. This is a single-node deployment; Docker restarts services after a host restart once Docker itself starts. It does not provide multi-host failover.

## Source contract

`SOURCE_URLS` is a comma-separated list of trusted HTTPS endpoints. Each must return HTTP 200 JSON with a `source` of `SANSA` and a `measurements` array. Each measurement needs `id`, `value`, `unit`, and a timezone-aware ISO 8601 `observedAt` originating from the instrument/source. Do not substitute the retrieval time.

Schema example only, deliberately historical and null (not a detection):

```json
{"source":"SANSA","measurements":[{"id":"wind","value":null,"unit":"km/s","observedAt":"2020-01-01T00:00:00Z"}]}
```

| ID | Measurement | Exact unit |
|---|---|---|
| wind | Solar wind speed | km/s |
| bz | IMF Bz | nT |
| dcx | Dcx | nT |
| fof2 | Hermanus foF2 | MHz |
| hmf2 | Hermanus hmF2 | km |
| tindex | T-index | empty string |

Partial responses are supported. Unknown channels, duplicate IDs, invalid units, nonnumeric values, absent timezones and timestamps over five minutes in the future are rejected. Range guards are basic input checks, not scientific calibration. Multiple endpoints may supply different subsets; conflicts at the same channel/time remain excluded with no automatic arbitration. A later valid observation can restore the channel.

The package does not scrape arbitrary HTML or assume an undocumented MoStar route implements this contract. If your actual upstream is HTML or a different JSON format, add and verify an adapter against original source responses first. The current raw archive preserves the configured endpoint's response; it cannot establish authenticity of a normalization service's underlying instruments. International comparison feeds and raw MeerKAT streams require separate adapters and source identities.

## Backups, updates and monitoring

Data lives in Docker's named `mostar-observatory_observations` volume, independently of containers. Do not use `docker compose down -v` unless you intend to erase data.

Create a consistent SQLite backup while services are running:

```bash
mkdir -p backups
docker compose exec app python service.py backup /data/backup.sqlite
docker compose cp app:/data/backup.sqlite backups/observatory.sqlite
```

Copy the backup off the VPS. Each command overwrites that backup name; archive dated copies externally if needed. For restoration, stop the collector and app, preserve the current volume first, and restore the backup into an empty observations volume owned by UID 10001. Never overwrite an active SQLite database or mix an old database with existing WAL sidecars.

Update code without removing the data volume:

```bash
git pull --ff-only
docker compose up -d --build
```

Use `--profile public` too when updating a public deployment. Monitor disk space, container restarts, acquisition attempts and `/readyz`; records currently have no automatic retention expiry. An unreachable source remains visibly degraded, with each failure recorded. External uptime alerts and backup scheduling must be configured on your VPS. The default freshness threshold is 30 minutes; choose `STALE_SECONDS` based on the actual source cadence.

## Development and verification

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/python -m unittest discover -s backend -v
cd frontend
npm ci
npm run build
cd ..
.venv/bin/python backend/service.py
```

Open http://localhost:8080. In another terminal, export `SOURCE_URLS` and start `.venv/bin/python backend/service.py collect`. For frontend development, run `npm run dev` inside `frontend`; its API proxy targets port 8080.

Tests use isolated temporary fixtures and never seed the production database. See `VERIFICATION.md` for checks actually performed during packaging and remaining deployment checks.

## Runtime credential isolation

Compose passes only named Observatory settings to each service. Keep Binance credentials in the separate Scaffs execution service. Never put trading keys in this repository or its Observatory environment files. Git and Docker ignore environment files; only the placeholder .env.example belongs in Git. Avoid sharing rendered Compose configuration because it can contain runtime values.
