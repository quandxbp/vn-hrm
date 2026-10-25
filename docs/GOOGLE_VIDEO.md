# Google Drive → YouTube

> **Hướng dẫn hiện tại:** [VIDEO_AUTOMATION.md](VIDEO_AUTOMATION.md), phiên bản **17.0.1.2.0**.
> Đã có tải Drive và resumable upload YouTube, hàng đợi, retry/hủy, callback theo domain.
> Xử lý nền và tự xếp hàng tắt; chờ chủ kênh cấp OAuth sau deploy. Nội dung dưới đây là lịch sử thiết lập ban đầu.

## Local setup — 24/10/2026

- Module `edu_video` 17.0.1.1.0 installed on local DB `gvnn`.
- Configuration: Trung tâm GVNN → Cấu hình → Google Drive / YouTube (system administrator).
- Direct local link: `http://localhost:8069/web?db=gvnn#action=268&id=1&model=edu.video.config&view_type=form`.
- OAuth Web application callback: `http://localhost:8069/edu-video/google/callback`.
- Enable Google Drive API and YouTube Data API v3. Add the connecting email to OAuth test users.
- Import the downloaded OAuth JSON, then use separate **Kết nối Google Drive** and **Kết nối / đổi kênh YouTube** buttons.
- Drive OAuth requests only Drive readonly. YouTube OAuth requests only YouTube upload and readonly scopes, with `prompt=select_account consent` to allow selecting a channel/Brand Account. The pending service is bound to session state; callback uses the appropriate token storage.
- YouTube connection verifies and displays the selected channel with `channels.list(mine=true)`, including `snippet.customUrl` as its handle. Optional expected-channel handle rejects the wrong channel before saving tokens.
- Default upload privacy setting is `unlisted`.
- User completed Google consent, but the original combined OAuth returned their personal channel. User requires **AU KIM NGAN @YUYONG90**. Local expected handle is now `@YUYONG90`; YouTube state cleared pending reconnection to this channel. Existing combined tokens are retained for Drive; new YouTube tokens use separate private fields. No videos uploaded.
- Secrets and tokens are stored in the local database; only system administrators can access the configuration. Token/secret fields have `base.group_no_one` field restrictions and are absent from views. Keep database backups private.
- `client_secret*.json` is excluded from Git. Do not include credentials or tokens in handoffs, logs or commits.
- Disconnect clears local tokens; users can also revoke access in their Google account.
- External OAuth apps in Testing have refresh tokens that expire after 7 days for these scopes.

## Scope and pending work

This version implements credential import, Google authorization, channel verification and local disconnect only. **It does not download or upload videos yet.**

Next: after user consent and confirmation of the target channel, implement background Drive download and resumable YouTube upload, session status/error/retry controls, automatic filling of `edu.session.youtube_url`, and optional automatic enqueue when saving a new Drive link. Preserve existing YouTube links and avoid duplicate uploads. No upload or automatic processing is currently enabled.

## Verification

Four mocked Odoo tests passed on an isolated clone of `gvnn`: credential import/disconnect, callback URI validation, non-admin access denial, and channel/scope validation. No real Google API upload occurred. The isolated test database was removed.

Callback troubleshooting: Google returned `error=access_denied` during the user's attempt. This response contains no authorization code and does not establish why consent was denied. The callback now distinguishes denial, missing code, other provider errors and expired/invalid state, with UTF-8 plain-text instructions and no-store/no-referrer headers. Two additional callback tests passed (six tests total); the second isolated test DB was removed. User needs to restart from **Kết nối Google**, verify the test-user email and finish the consent screen.

Version 1.1.0: eight mocked tests passed, including separate OAuth scope requests, channel handle rejection/match, and independent Drive/YouTube tokens. Test database `gvnn_google_split_check` removed. Pre-upgrade backup (contains OAuth secrets/tokens, keep private): `D:\Projects\vn-hrm-backups\youtube-channel-split-20261024\gvnn.dump`.

Pre-install backup: `D:\Projects\vn-hrm-backups\google-oauth-20261024\gvnn.dump`.
