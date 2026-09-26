# VPS deployment status — 2026-09-24

Target: root@31.97.180.251, /opt/mostar/observatory.
Requested hostname: moorb.mostarsystems.com.

Deployed from a tracked source archive plus the local deployment safeguards; no environment files were copied from the workstation. This VPS directory is an extracted release, not a Git checkout. Changes have not been pushed to GitHub.

Verified on the VPS:
- Clean Docker build and frontend production build passed.
- App container is healthy, bound only to 127.0.0.1:8080.
- Dashboard and /healthz return 200.
- All nine backend tests pass inside the production image.
- /readyz returns 503 as expected without a verified feed.
- Persistent observations volume, unless-stopped restart policy, enabled Docker service, and mode 600 runtime .env.

Collector is intentionally not started: SOURCE_URLS is empty. No Binance credentials are provided to Observatory.

The existing Nginx gateway owns ports 80/443. The Compose public/Caddy profile must not be started on this host. A dedicated HTTP virtual host is installed at /etc/nginx/http.d/moorb.mostarsystems.com.conf for ACME and HTTPS redirects; nginx -t and reload passed. Existing services and firewall rules were preserved.

DNS and HTTPS completed: moorb.mostarsystems.com resolves to 31.97.180.251. A valid Let's Encrypt certificate expires 2026-12-23. Nginx SNI routing terminates TLS at 127.0.0.1:15443 and protects the app with basic authentication. Authenticated dashboard and /healthz return 200; /readyz returns 503 without a feed. External unauthenticated HTTPS returns 401. Certbot renewal timer is active, with an Nginx reload hook. Access credentials are stored only on the VPS in /root/moorb-access.txt (root-only); retrieve through SSH. Do not rerun the one-time TLS setup script.

The dependency installation reported one high-severity npm audit finding; it has not been investigated or remediated in this deployment.

Certificate renewal dry-run passed for moorb.mostarsystems.com.
