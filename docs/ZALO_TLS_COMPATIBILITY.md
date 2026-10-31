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
