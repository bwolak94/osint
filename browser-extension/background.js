/**
 * OSINT Platform - Background Service Worker
 *
 * Handles context menus and message routing between content script and
 * the OSINT Platform web app.
 */

const DEFAULT_PLATFORM_URL = 'http://localhost:8080';

// ── Context menu setup ──────────────────────────────────────────────────────

const MENU_ITEMS = [
  { id: 'osint-ip',       title: 'Investigate IP in OSINT Platform',       type: 'ip' },
  { id: 'osint-domain',   title: 'Investigate Domain in OSINT Platform',   type: 'domain' },
  { id: 'osint-email',    title: 'Investigate Email in OSINT Platform',    type: 'email' },
  { id: 'osint-username', title: 'Investigate Username in OSINT Platform', type: 'username' },
];

chrome.runtime.onInstalled.addListener(() => {
  // Remove stale menus from previous install before recreating
  chrome.contextMenus.removeAll(() => {
    for (const item of MENU_ITEMS) {
      chrome.contextMenus.create({
        id: item.id,
        title: item.title,
        contexts: ['selection'],
      });
    }
  });
});

// ── Context menu click handler ──────────────────────────────────────────────

chrome.contextMenus.onClicked.addListener((info, _tab) => {
  const selectedText = (info.selectionText ?? '').trim();
  if (!selectedText) return;

  const menuItem = MENU_ITEMS.find((m) => m.id === info.menuItemId);
  if (!menuItem) return;

  openInPlatform(selectedText, menuItem.type);
});

// ── Message handler (from content.js) ──────────────────────────────────────

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === 'OSINT_INVESTIGATE') {
    const { value, entityType } = message;
    openInPlatform(value, entityType);
    sendResponse({ ok: true });
  }
  // Must return true if sendResponse will be called asynchronously
  return false;
});

// ── Helpers ─────────────────────────────────────────────────────────────────

/**
 * Opens the OSINT Platform new-investigation page pre-filled with the target.
 */
function openInPlatform(target, type) {
  chrome.storage.sync.get({ platformUrl: DEFAULT_PLATFORM_URL }, ({ platformUrl }) => {
    const base = platformUrl.replace(/\/$/, '');
    const params = new URLSearchParams({ target, type });
    const url = `${base}/investigations/new?${params.toString()}`;

    chrome.tabs.create({ url });

    // Persist to recent investigations (max 10, newest first)
    chrome.storage.local.get({ recentInvestigations: [] }, ({ recentInvestigations }) => {
      const entry = { target, type, url, timestamp: Date.now() };
      const updated = [entry, ...recentInvestigations.filter((r) => r.target !== target || r.type !== type)].slice(0, 10);
      chrome.storage.local.set({ recentInvestigations: updated });
    });
  });
}
