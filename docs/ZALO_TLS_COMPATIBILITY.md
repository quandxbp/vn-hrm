# Zalo TLS compatibility

On 31 October 2026, production's Node 22 default HTTPS connection to
`wpa.chat.zalo.me` timed out with `UND_ERR_CONNECT_TIMEOUT`. TCP port 443
was reachable and HTTPS to Google worked from the same container. Windows
HTTPS and Node HTTPS limited to TLS 1.2 both reached the Zalo endpoint.
With `node --tls-max-v1.2`, login using the existing stored credentials and
reading the group list both succeeded.

The Compose command applies this compatibility setting only to the Zalo
bridge process. Certificate verification stays enabled. No credentials,
volumes, delivery ledger or Odoo services need to change. Revisit the setting
when the default TLS handshake works reliably on this network.

Deploy with `docker compose --profile zalo up -d --no-deps zalo-bridge`.
Verify both `/status` and an authenticated read of `/groups`: the status flag
alone only reports the last successful login and cannot prove live connectivity.
Never use `/messages` as a connectivity test.

The 31 October daily receipt was uncertain with zero confirmed message IDs.
The user confirmed the group had not received it and authorized a replacement
send. Preserve that receipt and the bridge ledger. Resolve the Odoo receipt
with this explicit user confirmation before creating a separate manual send;
do not delete or reuse the original bridge request key.

## Reliability safeguards (31 October 2026)

- Authenticated `GET /check` probes group access, rather than trusting a cached
  login flag. A failed probe reconnects once with stored credentials and probes
  again. Probes and sends have bounded waits. A failed probe creates no delivery
  intent and may safely be retried with the same request key.
- After `sendMessage` starts, errors/timeouts are always uncertain. Store only a
  safe error code, retain partial IDs and never automatically repeat that key.
  The bridge ledger remains authoritative after an Odoo timeout or restart.
- Odoo retries failed requests with their original immutable content/key, after
  1, 2, 4, 8, then 15 minutes, capped at 12 attempts. Old failures without a
  scheduled retry are not reactivated on upgrade. A later successful replacement
  suppresses retries of the earlier daily request.
- Automatic catch-up defaults to six hours after the configured send time,
  strictly within the same Vietnam calendar day. No automatic previous-day send.
  The manager may configure the window between 0.5 and 12 hours.
- Every five minutes, while automatic sending is enabled, Odoo checks live
  connectivity and today's delivery. Problems create a persistent activity for
  the configured responsible user and a warning in the configuration screen.
  The activity is deduplicated, then completed after confirmed recovery. A queued
  message more than five minutes old also triggers a warning.

This monitoring runs in Odoo's cron and requires Odoo, PostgreSQL and the server
to be running. It cannot alert during a total server outage. An independent
external uptime/notification service is needed for that failure mode. Zalo is
an unofficial external API, so permanent availability or exactly-once delivery
cannot be guaranteed when an upstream send result is ambiguous.
