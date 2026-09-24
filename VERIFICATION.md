# Packaging verification

- Nine backend tests passed: empty state, deduplication, conflict exclusion, evidence retention on rejection, stale samples, null handling, timestamp alignment, liveness versus readiness, source/timezone rejection.
- Frontend production build passed with Vite 8.0.13 using the available local dependency installation. A package lock is included for clean `npm ci` builds; a clean container build remains to be checked on the VPS.
- Docker image and Compose deployment: not run here because Docker is unavailable in this environment. Validate with `docker compose config --quiet` and `docker compose up -d --build` on the VPS.
- External feed, TLS domain, VPS reboot persistence and off-host backup restoration: require deployment-time verification. No successful live upstream ingestion is claimed.
