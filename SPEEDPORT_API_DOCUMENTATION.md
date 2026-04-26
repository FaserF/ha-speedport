# Telekom Speedport API & Authentication Documentation

This document describes the technical inner workings of the authentication process for Telekom Speedport routers and how this integration interacts with them.

## 1. Authentication Variants

Telekom Speedport routers (primarily manufactured by Arcadyan, Zyxel, or Huawei) use two main authentication schemes depending on their generation.

### A. Legacy Authentication (MD5)
*Used by: W 724V, Entry 2, Smart 1/2 (partially)*

This is a traditional session-based approach:
1. **Token Acquisition**: The client first requests the login page (`/html/login/index.html`) to obtain a CSRF token (often called `httoken` or `token`).
2. **MD5 Hashing**: The user's password is hashed using MD5.
3. **Login POST**: The client sends a POST request to `/data/Login.json` with the hashed password and the token.
4. **Session Cookie**: Upon success, the router sets a session cookie (usually `SessionID` or `set-cookie`). This cookie must be included in all subsequent requests.

### B. Modern Authentication (Challenge-Response / Encrypted)
*Used by: Smart 3, Smart 4, Pro, Pro Plus*

This is a much more secure, hardware-accelerated process:
1. **Challenge Request**: The client requests `/data/Login.json` (GET). The router returns a `challenge` string.
2. **Key Derivation (PBKDF2)**: The client derives a 256-bit key from the user's password and the challenge using PBKDF2 (often with 1000+ iterations).
3. **Encrypted Communication (AES-CCM)**: 
   - Every subsequent request is no longer plain JSON.
   - The JSON payload is encrypted using **AES-256-CCM**.
   - The request body is sent as a raw hex string.
   - The response is also a hex string that must be decrypted using the same derived key.
4. **Token Refresh**: A `challenge` (nonce) is used for every request to prevent replay attacks.

---

## 2. Session Management & Cookies

### The "Hidden" Session
Speedports are notoriously strict about "Double Logins". If a user is logged into the web interface, the API will often return a "Document Moved" or "Busy" error. 

Our integration handles this by:
- **Persistent Sessions**: We maintain the same `aiohttp` session and cookie jar.
- **Auto-Login**: If a request returns a redirect to the login page, the integration automatically triggers a re-authentication.
- **Referer Headers**: Many Speedport endpoints (especially on legacy models) strictly validate the `Referer` header. We spoof these headers (e.g., `html/content/overview/index.html`) to mimic a real browser user.

### JSON Structure
Speedport APIs usually return data in one of two formats:
1. **Standard Object**: `{"key": "value"}`
2. **Flat List (Legacy)**: A list of objects like `[{"varid": "status", "varvalue": "ok"}]`.
   - The integration contains a `_simplify_response` helper that flattens these lists into standard dictionaries for easier processing.

---

## 3. How we "Abuse" the API

We utilize the same endpoints that the router's own web interface uses. Since the web interface is a Single Page Application (SPA), it communicates with the backend via JSON files in the `/data/` directory.

### Key Endpoints:
- `data/Status.json`: Basic connectivity status (public IPs, DSL sync).
- `data/Overview.json`: General system info (Firmware, Model, Serial).
- `data/Login.json`: Used for both getting the initial challenge and performing the login.
- `data/DeviceList.json`: List of all connected LAN/WLAN devices.
- `data/HomeNetwork.json`: Alternative source for device and topology data on newer models.

### Bypassing Restrictions:
- **Root Access**: On older models, we can sometimes access `/data/` files without a full login if we provide the correct referer.
- **Multi-Source Fetching**: Because different models store the same info under different keys (e.g., `firmware_version` vs. `domain_name`), we perform "Key Mining" — we fetch multiple JSON files and merge them, allowing the integration to work across almost all Speedport generations.

---

## 4. Implementation Details in Python

The `api.py` file implements the `SpeedportClient`:
- **MD5 Logic**: Uses the `hashlib` library for legacy models.
- **AES-CCM Logic**: Uses `pycryptodome` for modern models.
- **Timing**: We append `_time` and `_rand` parameters to URLs to bypass router-side caching.
- **Robustness**: The integration detects if a response is Hex (encrypted) or JSON (plain) on the fly, allowing it to adapt to the router's security level automatically.
