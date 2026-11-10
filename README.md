# Linka Chat

A responsive messaging web app for laptop browsers, Android and iPhone, with phone-number accounts, saved contacts, group chats, attachments, 24-hour statuses, and an optional AI assistant.

**This is an early, self-hosted application, not a WhatsApp-equivalent security implementation.** Messages are NOT end-to-end encrypted. Phone numbers are account identifiers and are NOT verified by SMS. Do not present them as verified identities. This project is not affiliated with WhatsApp.

## Run locally — Windows

1. Install Python **3.11 or newer** from python.org.
2. Extract the ZIP.
3. Open a terminal inside the folder containing `server.py`.
4. Run `python server.py` (or double-click `start.bat`).
5. Visit **http://localhost:8080** in your browser.
6. Create an account using a country-code number (e.g. `+94771234567`) and a password of at least 12 characters.

macOS/Linux: `python3 server.py` or `sh start.sh`.

No pip packages, Node installation or build step are required to run the server. SQLite stores app data in `data/linka.sqlite3`. Do not delete that directory if you want to keep accounts and messages. Back it up securely; the database contains readable private messages.

## Talk to a friend

Both people must use **the same running deployment**. Accounts on different local installations do not connect.

1. Both people create Linka accounts.
2. Click **+ → Save phone number** and add the other person's registered number.
3. Select a saved contact and start a direct chat. Select multiple contacts or enter a group name to create a group.
4. Messages refresh approximately every 3 seconds while the page is visible. The most recent 200 messages are displayed.
5. Open **Updates** above the chat list to share text or a photo. Statuses are visible only to **mutual saved contacts** and expire after 24 hours. Old records are removed on the next status request; no background cleanup service is included.

Contacts are entered manually. This app does not read your phone address book, send SMS, or connect to the WhatsApp network.

## Put the project on GitHub

Create a new empty repository. Upload the **contents** of this folder (including `public`, `tests`, `server.py`, `Dockerfile`, README and the hidden configuration files) to the repository root, then commit. Do not upload `data/`, `.env`, passwords, AI keys, or database files.

**GitHub stores the source; GitHub Pages cannot run this Python backend.** Deploy the repository on a Python/Docker host with persistent storage. A backend host is necessary for other people to sign in and chat over the Internet.

### Production deployment requirements

- Python 3.11+ or build the supplied Dockerfile.
- Start command: `python server.py`.
- Expose the host-provided `PORT` (default 8080).
- Configure an HTTPS domain and a trusted reverse proxy.
- Set `PRODUCTION=1` to enable Secure session cookies and HSTS.
- Set `PUBLIC_ORIGIN` to your exact public origin, e.g. `https://chat.example.com` (no trailing slash).
- Mount a writable persistent directory and set `DATA_DIR` to it, e.g. `/data`.
- Run a **single server instance** with the SQLite database on persistent local storage. Do not horizontally scale this version.
- Keep the origin server private behind your HTTPS proxy. Do not expose the development HTTP server directly to the public Internet.

The `.env.example` file documents environment variables. The server does not automatically load `.env`; set variables through your host or terminal.

Docker example, after replacing the domain:

```sh
docker build -t linka-chat .
docker run -p 8080:8080 -v linka-data:/data -e PRODUCTION=1 -e PUBLIC_ORIGIN=https://chat.example.com linka-chat
```

You still need your HTTPS reverse proxy and DNS. Your host may charge for persistent storage, networking, or compute.

## Install on Android / iPhone / laptop

Once deployed over **HTTPS**, open the app in a browser:

- **Android Chrome:** browser menu → Install app / Add to Home screen.
- **iPhone Safari:** Share → Add to Home Screen → Add.
- **Desktop Chrome/Edge:** use the browser's Install app control when available.

This is a **PWA**, not an APK, IPA, App Store or Play Store build. It requires a network connection for chat and sign-in. No private data is cached by the service worker. Browser install UI depends on browser version and policy.

## Optional AI assistant

Click the sparkle icon in the left rail. To enable real AI responses, configure `OPENAI_API_KEY` **only on the server**, optionally `OPENAI_MODEL`, then restart. Never put an API key in JavaScript, a public repository, or `public/`.

The assistant sends only the typed prompt to OpenAI after the user checks the explicit consent box. It does not automatically read contacts, messages, or statuses. Without an API key, it reports that AI is not configured. AI provider usage may incur charges; ChatGPT subscriptions do not configure this server. The app currently uses the Chat Completions API and a configurable model; confirm model availability in your provider account.

## Security and scope

Implemented: scrypt salted password hashes, random sessions stored as token hashes, HttpOnly/SameSite cookies, Secure cookies in production, room membership authorization, same-origin POST checks, input/file restrictions, per-IP request limits, member-only message reads, mutual-contact statuses, and message blocking.

Limitations: no E2EE, no SMS verification or phone ownership proof, no password recovery, no MFA, no independent security audit, no encrypted backups, no push notifications, no voice/video calls, no actual delivery/read receipts, no online presence tracking, no automatic address-book import, no cross-server federation, and no unblock UI in this release. Blocking preserves old messages and prevents incoming messages from the blocked account. Live message deletion is not available. Group membership is fixed at creation. Files are limited to 1 MB (PNG, JPEG, WebP, PDF or text); statuses accept images only. No virus scanning is included.

Phone number lookup intentionally reveals whether a number is registered when a signed-in user adds a contact. Registration ownership is not verified; do not use this for identity-sensitive communication. App/database administrators can read stored content. Rate limiting is in-process and per IP; a production-scale service needs a shared rate limiter, abuse reporting/moderation and further review. Private messages and statuses must not be used as public test data.

## Tests

```sh
python -m unittest discover -s tests -v
node --check public/enhancements.js
```

The integration test creates two accounts in a temporary database and checks sign-in, cookie attributes, contact lookup, two-person messaging, room isolation, cross-origin rejection, mutual-contact status visibility, status expiry, ownership checks, attachment validation, blocking and session logout. GitHub Actions runs these checks. Automated tests do not constitute an independent security audit.

## File map

- `server.py` — HTTP API, account/session handling and SQLite persistence.
- `public/index.html` — responsive chat interface and device-only demo.
- `public/enhancements.js` — live account, contact, chat, status and AI flows.
- `public/manifest.webmanifest`, `sw.js`, icons — PWA support.
- `tests/test_server.py` — integration tests.
- `Dockerfile`, `.env.example`, startup scripts — deployment and local run support.
- `preview.html` — downloadable single-file visual/demo preview. Real accounts require `server.py`.

## සිංහලෙන් ඉක්මන් උපදෙස්

ZIP එක extract කරලා `start.bat` open කරන්න. Browser එකේ `http://localhost:8080` යන්න. Sign up කරලා friendගේ **මේ app එකේ register වුණු** number එක save කරන්න. දෙන්නාම එකම server එක භාවිත කරන්න ඕනේ.

GitHub එකට code upload කළාට පමණක් Internet chat වැඩ කරන්නේ නැහැ. Python backend එක HTTPS සහ persistent storage තියෙන host එකකට deploy කරන්න. Android/iPhone වල browser එකෙන් Add to Home Screen කරන්න පුළුවන්. මෙය WhatsApp වගේ E2EE හෝ SMS verification සහිත සම්පූර්ණ production සේවාවක් නොවේ.
