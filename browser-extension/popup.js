/**
 * OSINT Platform - Popup Script
 *
 * Manages:
 *  - Platform URL setting (chrome.storage.sync)
 *  - Quick-investigate form
 *  - Recent investigations list (chrome.storage.local, max 10)
 */

'use strict';

const DEFAULT_URL = 'http://localhost:8080';

// ── DOM refs ──────────────────────────────────────────────────────────────

const platformUrlInput = /** @type {HTMLInputElement} */ (document.getElementById('platform-url'));
const saveUrlBtn       = document.getElementById('save-url');
const saveMsg          = document.getElementById('save-msg');
const targetInput      = /** @type {HTMLInputElement} */ (document.getElementById('target-input'));
const typeSelect       = /** @type {HTMLSelectElement} */ (document.getElementById('type-select'));
const openBtn          = document.getElementById('open-btn');
const recentList       = document.getElementById('recent-list');

// ── Init ──────────────────────────────────────────────────────────────────

chrome.storage.sync.get({ platformUrl: DEFAULT_URL }, ({ platformUrl }) => {
  platformUrlInput.value = platformUrl;
});

loadRecent();

// ── Platform URL ──────────────────────────────────────────────────────────

saveUrlBtn.addEventListener('click', () => {
  const url = platformUrlInput.value.trim().replace(/\/$/, '');
  if (!url) return;
  chrome.storage.sync.set({ platformUrl: url }, () => {
    saveMsg.classList.add('visible');
    setTimeout(() => saveMsg.classList.remove('visible'), 1800);
  });
});

platformUrlInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') saveUrlBtn.click();
});

// ── Quick investigate ─────────────────────────────────────────────────────

openBtn.addEventListener('click', () => {
  const target = targetInput.value.trim();
  if (!target) return;
  const type = typeSelect.value;
  openInPlatform(target, type);
});

targetInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') openBtn.click();
});

// ── Helpers ───────────────────────────────────────────────────────────────

/**
 * Opens the platform new-investigation page and persists the entry to recent.
 */
function openInPlatform(target, type) {
  chrome.storage.sync.get({ platformUrl: DEFAULT_URL }, ({ platformUrl }) => {
    const base = platformUrl.replace(/\/$/, '');
    const params = new URLSearchParams({ target, type });
    const url = `${base}/investigations/new?${params.toString()}`;

    chrome.tabs.create({ url });

    // Persist
    chrome.storage.local.get({ recentInvestigations: [] }, ({ recentInvestigations }) => {
      const entry = { target, type, url, timestamp: Date.now() };
      const deduped = recentInvestigations.filter((r) => !(r.target === target && r.type === type));
      const updated = [entry, ...deduped].slice(0, 10);
      chrome.storage.local.set({ recentInvestigations: updated }, loadRecent);
    });
  });
}

/**
 * Renders the recent investigations list from storage.
 */
function loadRecent() {
  chrome.storage.local.get({ recentInvestigations: [] }, ({ recentInvestigations }) => {
    if (recentInvestigations.length === 0) {
      recentList.innerHTML = '<li class="empty-msg">No recent investigations</li>';
      return;
    }

    recentList.innerHTML = '';
    for (const item of recentInvestigations) {
      const li = document.createElement('li');
      li.className = 'recent-item';
      li.title = item.url;

      const badge = document.createElement('span');
      badge.className = 'recent-badge';
      badge.textContent = item.type;

      const value = document.createElement('span');
      value.className = 'recent-value';
      value.textContent = item.target;

      const time = document.createElement('span');
      time.className = 'recent-time';
      time.textContent = formatRelativeTime(item.timestamp);

      li.appendChild(badge);
      li.appendChild(value);
      li.appendChild(time);

      li.addEventListener('click', () => {
        chrome.tabs.create({ url: item.url });
      });

      recentList.appendChild(li);
    }
  });
}

/**
 * Returns a human-readable relative time string.
 * @param {number} timestamp
 * @returns {string}
 */
function formatRelativeTime(timestamp) {
  const diff = Date.now() - timestamp;
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1)  return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24)   return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
