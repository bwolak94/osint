/**
 * OSINT Platform - Content Script
 *
 * Watches for text selections. When selected text matches a known OSINT
 * entity pattern (IP, email, domain) a small floating bubble appears near
 * the selection offering one-click investigation shortcuts.
 */

(function () {
  'use strict';

  // ── Patterns ──────────────────────────────────────────────────────────────

  const PATTERNS = {
    ip:     /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/,
    email:  /^.+@.+\..+$/,
    domain: /^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z]{2,})+$/i,
  };

  // ── Styles injected once ──────────────────────────────────────────────────

  const STYLE_ID = 'osint-bubble-style';

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      #osint-bubble {
        position: fixed;
        z-index: 2147483647;
        display: flex;
        align-items: center;
        gap: 4px;
        padding: 4px 8px;
        background: #18181b;
        border: 1px solid #3f3f46;
        border-radius: 8px;
        box-shadow: 0 4px 16px rgba(0,0,0,.45);
        font-family: system-ui, sans-serif;
        font-size: 11px;
        color: #a1a1aa;
        pointer-events: all;
        user-select: none;
        transition: opacity .15s;
      }
      #osint-bubble .osint-label {
        margin-right: 4px;
        white-space: nowrap;
        color: #71717a;
      }
      #osint-bubble button {
        display: inline-flex;
        align-items: center;
        gap: 3px;
        padding: 2px 7px;
        background: #27272a;
        border: 1px solid #3f3f46;
        border-radius: 5px;
        color: #e4e4e7;
        font-size: 11px;
        cursor: pointer;
        transition: background .1s, border-color .1s;
        white-space: nowrap;
      }
      #osint-bubble button:hover {
        background: #6366f1;
        border-color: #6366f1;
        color: #fff;
      }
      #osint-bubble .osint-close {
        margin-left: 4px;
        background: transparent;
        border: none;
        color: #52525b;
        padding: 2px 4px;
        font-size: 13px;
        line-height: 1;
      }
      #osint-bubble .osint-close:hover {
        background: #3f3f46;
        color: #e4e4e7;
      }
    `;
    document.head.appendChild(style);
  }

  // ── Bubble element ────────────────────────────────────────────────────────

  let bubble = null;

  function removeBubble() {
    if (bubble) {
      bubble.remove();
      bubble = null;
    }
  }

  function createBubble(text, matches, x, y) {
    removeBubble();
    injectStyles();

    bubble = document.createElement('div');
    bubble.id = 'osint-bubble';

    const label = document.createElement('span');
    label.className = 'osint-label';
    label.textContent = 'Investigate:';
    bubble.appendChild(label);

    for (const type of matches) {
      const btn = document.createElement('button');
      btn.textContent = BUTTON_LABELS[type];
      btn.title = `Investigate as ${type} in OSINT Platform`;
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        chrome.runtime.sendMessage({ type: 'OSINT_INVESTIGATE', value: text, entityType: type });
        removeBubble();
      });
      bubble.appendChild(btn);
    }

    const closeBtn = document.createElement('button');
    closeBtn.className = 'osint-close';
    closeBtn.textContent = '✕';
    closeBtn.title = 'Dismiss';
    closeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      removeBubble();
    });
    bubble.appendChild(closeBtn);

    document.body.appendChild(bubble);

    // Position bubble: prefer above-right of selection, clamp to viewport
    const bw = 300; // estimated width before render
    const bh = 36;  // estimated height
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    let left = Math.min(x + 4, vw - bw - 12);
    let top  = Math.max(y - bh - 8, 8);

    bubble.style.left = `${left}px`;
    bubble.style.top  = `${top}px`;
  }

  const BUTTON_LABELS = {
    ip:     '🔍 IP',
    email:  '✉ Email',
    domain: '🌐 Domain',
  };

  // ── Selection listener ────────────────────────────────────────────────────

  function detect(text) {
    const trimmed = text.trim();
    if (!trimmed || trimmed.length > 253) return [];
    return Object.entries(PATTERNS)
      .filter(([, re]) => re.test(trimmed))
      .map(([type]) => type);
  }

  document.addEventListener('mouseup', (e) => {
    // Small delay so the selection range is finalised
    setTimeout(() => {
      const sel = window.getSelection();
      const text = sel ? sel.toString().trim() : '';

      if (!text) {
        removeBubble();
        return;
      }

      const matches = detect(text);
      if (matches.length === 0) {
        removeBubble();
        return;
      }

      createBubble(text, matches, e.clientX, e.clientY);
    }, 50);
  });

  // Remove bubble on click-elsewhere or scroll
  document.addEventListener('mousedown', (e) => {
    if (bubble && !bubble.contains(e.target)) removeBubble();
  });

  document.addEventListener('scroll', removeBubble, true);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') removeBubble();
  });
})();
