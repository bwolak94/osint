# OSINT Platform Browser Extension

One-click investigation from any webpage directly into the OSINT Platform.

## Features

- **Right-click context menu** — select any text and choose *Investigate IP / Domain / Email / Username in OSINT Platform*.
- **Selection bubble** — when selected text matches an IP, email, or domain pattern, a small floating toolbar appears near the selection with direct investigation buttons.
- **Quick-investigate popup** — click the extension icon to investigate any target manually.
- **Recent investigations** — the last 10 targets are stored locally for quick re-access.

## Installation (Chrome / Edge / Brave)

1. Open `chrome://extensions` in your browser.
2. Enable **Developer mode** (top-right toggle).
3. Click **Load unpacked**.
4. Select the `browser-extension/` folder from this repository.
5. The extension icon appears in your toolbar.

> **Note:** Icons (`icons/icon16.png` and `icons/icon48.png`) are referenced by the manifest but not included in this repository. Create or drop 16×16 and 48×48 PNG files in the `icons/` folder before loading. The extension loads without them but Chrome will show a placeholder.

## Configuration

1. Click the extension icon to open the popup.
2. In the **Platform URL** field, enter the base URL of your running OSINT Platform instance (default: `http://localhost:8080`).
3. Click **Save**.

## Usage

### Right-click menu
1. Select any text on a webpage.
2. Right-click → choose the appropriate *Investigate … in OSINT Platform* option.
3. A new tab opens on the platform's new-investigation page pre-filled with your target.

### Selection bubble
Select text that looks like an IP address (`8.8.8.8`), email (`user@example.com`), or domain (`example.com`). A small bubble appears — click the matching button to open the platform.

### Popup quick-investigate
1. Click the extension icon.
2. Type a target, choose the entity type, click **Open**.
