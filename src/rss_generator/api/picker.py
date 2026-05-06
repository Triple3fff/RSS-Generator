import json
import re
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import HTMLResponse

from ..scraper.fetcher import fetch_page
from ..config import settings

router = APIRouter(tags=["picker"])

# Injected before PICKER_SCRIPT when saved selectors are present.
# {init_json} is replaced with a safe JSON literal.
_INIT_SCRIPT = '<script>window.__RSS_INIT__={init_json};</script>\n'

PICKER_SCRIPT = r"""
<style id="__rss_picker_style">
  html { margin-top: 52px !important; }
  .__ph  { outline: 2px solid #f97316 !important; background: rgba(249,115,22,0.07) !important; }
  .__phc { outline: 2px dashed #8b5cf6 !important; background: rgba(139,92,246,0.08) !important; }
  .__phx { outline: 2px dashed #ef4444 !important; background: rgba(239,68,68,0.10) !important; opacity: 0.55; }
  .__phf { outline: 2px solid #22c55e !important; background: rgba(34,197,94,0.10) !important; }
  .__pm {
    position: fixed; background: #fff; border: 1px solid #e5e7eb;
    border-radius: 8px; box-shadow: 0 8px 24px rgba(0,0,0,0.18);
    padding: 6px; z-index: 2147483647; font-family: system-ui,sans-serif;
    font-size: 13px; min-width: 200px; pointer-events: auto;
  }
  .__pm button {
    display: block; width: 100%; text-align: left; padding: 6px 10px;
    border: none; background: none; cursor: pointer; border-radius: 4px;
    color: #374151; font-size: 13px; font-family: inherit;
  }
  .__pm button:hover { background: #f3f4f6; }
  .__pm-sep { border-top: 1px solid #f3f4f6; margin: 4px 0; }
  .__pm-info { padding: 4px 10px 6px; font-size: 11px; color: #9ca3af; word-break: break-all; max-width: 240px; }
  .__tb {
    position: fixed; top: 0; left: 0; right: 0; height: 52px;
    background: #111827; color: #fff; display: flex; align-items: center;
    gap: 8px; padding: 0 12px; z-index: 2147483646;
    font-family: system-ui,sans-serif; font-size: 12px; box-sizing: border-box;
    pointer-events: auto; flex-wrap: wrap;
  }
  .__tb-title  { font-weight: 700; color: #f97316; font-size: 13px; white-space: nowrap; }
  .__tb-hint   { color: #9ca3af; font-size: 11px; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .__tb-fields { display: flex; gap: 6px; flex-wrap: wrap; }
  .__tb-f      { font-size: 11px; }
  .__tb-f.done { color: #4ade80; }
  .__tb-f.auto { color: #60a5fa; }
  .__tb-f.pend { color: #6b7280; }
  .__tb-show   { padding: 4px 10px; background: #065f46; border: 1px solid #059669; border-radius: 5px; color: #6ee7b7; cursor: pointer; font-size: 12px; white-space: nowrap; }
  .__tb-save   { padding: 4px 10px; background: #f97316; border: none; border-radius: 5px; color: #fff; cursor: pointer; font-weight: 600; font-size: 12px; white-space: nowrap; }
  .__tb-cancel { padding: 4px 8px; background: #374151; border: 1px solid #4b5563; border-radius: 5px; color: #fff; cursor: pointer; font-size: 12px; }
  /* Crosshair cursor over the whole page; restore default inside our own widgets */
  body { cursor: crosshair !important; }
  body .__tb, body .__tb *, body .__pm, body .__pm * { cursor: default !important; }
  body .__pm button { cursor: pointer !important; }
  /* Override A/B-testing anti-flicker patterns (Intellimize, Optimizely, VWO, Google Optimize).
     These tools add a class to <html> that hides the entire page while their CDN script loads
     and applies the test variant.  In the picker iframe the CDN fetch fails (null origin) so
     the page may stay hidden until the tool's built-in timeout fires (up to 4 s).
     Our rules have higher specificity than the tool's generic class selectors, so they win. */
  html.anti-flicker, html.anti-flicker * { visibility: visible !important; opacity: 1 !important; }
  html.optimizely-force-hide, html.optimizely-force-hide * { visibility: visible !important; opacity: 1 !important; }
  html.vwo-anti-flicker, html.vwo-anti-flicker * { visibility: visible !important; opacity: 1 !important; }
  html.async-hide, html.async-hide * { opacity: 1 !important; }
</style>
<script id="__rss_picker_script">
(function() {
  /* ── State ── */
  var sel = {};
  var container    = null;
  var containerSel = '';
  var containerBase = '';
  var excludedEls  = [];
  var manuallyIncluded = [];
  var savedExcludedNths = [];  // nth-of-type indices from the stored :not() clauses
  var _restoredEls = [];       // elements with restoration inline styles (for clearing)
  var _highlightsShowing = false;
  var _origContainerSel = '';       // original selector_item from init (may have :not() from old saves)

  var fields = [
    { key: 'selector_item',        label: 'Container',   icon: '▦',  req: true  },
    { key: 'selector_title',       label: 'Title',       icon: 'T',  req: true  },
    { key: 'selector_description', label: 'Description', icon: '¶',  req: false },
    { key: 'selector_date',        label: 'Date',        icon: '⏰', req: false },
    { key: 'selector_author',      label: 'Author',      icon: '👤', req: false },
  ];

  /* ── Toolbar ── */
  var tb = document.createElement('div'); tb.className = '__tb';
  tb.innerHTML =
    '<span class="__tb-title">RSS Picker</span>' +
    '<span class="__tb-hint" id="__tb_hint">Click an element, then assign it</span>' +
    '<div class="__tb-fields" id="__tb_f"></div>' +
    '<button class="__tb-show" id="__tb_show" style="display:none">◉ Previous Selections</button>' +
    '<button class="__tb-save" id="__tb_ok">Save</button>' +
    '<button class="__tb-cancel" id="__tb_x">Cancel</button>';
  document.body.appendChild(tb);

  function refreshTb() {
    var hint = document.getElementById('__tb_hint');
    var fc   = document.getElementById('__tb_f');
    if (!container) {
      hint.textContent = 'Click an article element and assign it as Container or Title';
      fc.innerHTML = '';
      return;
    }
    var cnt = 0;
    try { cnt = document.querySelectorAll(containerSel).length; } catch(e) {}
    hint.textContent = '▦ ' + containerSel + ' (' + cnt + ' items)' + (sel.selector_link ? '  🔗 auto' : '');
    fc.innerHTML = fields.map(function(f) {
      var done = !!sel[f.key];
      return '<span class="__tb-f ' + (done ? 'done' : 'pend') + '">' + (done ? '✓' : '○') + ' ' + f.label + '</span>';
    }).join('');
  }
  refreshTb();

  document.getElementById('__tb_ok').onclick = function() {
    window.parent.postMessage({ type: 'rss-picker-done', selectors: sel }, '*');
  };
  document.getElementById('__tb_x').onclick = function() {
    window.parent.postMessage({ type: 'rss-picker-cancel' }, '*');
  };

  /* ── Show Selections button — toggle on/off ── */
  document.getElementById('__tb_show').onclick = function() {
    if (_highlightsShowing) { hideSelections(); } else { showSelections(); }
  };

  /* ── Utilities ── */
  function goodClass(c) {
    if (c.length <= 1) return false;
    // State / JS-hook classes
    if (/^(active|hover|focus|open|visible|hidden|show|selected|current|first|last|odd|even|disabled|loading|mounted|ready|init|initialized)$/.test(c)) return false;
    if (/^(is-|has-|js-|was-|will-)/.test(c)) return false;
    // Internal / hash-like
    if (/^__/.test(c)) return false;
    if (/\d{3,}/.test(c)) return false;
    // Tailwind responsive / variant prefixes (contain a colon, e.g. "md:flex", "hover:bg-blue-500")
    if (c.indexOf(':') >= 0) return false;
    // Tailwind layout / display utilities
    if (/^(flex|grid|block|inline|hidden|table|contents|list-item|flow-root)$/.test(c)) return false;
    if (/^(relative|absolute|fixed|sticky|static)$/.test(c)) return false;
    if (/^(overflow|truncate|sr-only|not-sr-only|clearfix|float|clear|isolate|isolation)$/.test(c)) return false;
    // Tailwind utility prefixes — flexbox, grid, sizing, spacing, colour, etc.
    if (/^(flex-|grid-|col-|row-|gap-|space-|order-|place-)/.test(c)) return false;
    if (/^(items-|justify-|self-|align-|content-)/.test(c)) return false;
    if (/^(w-|h-|min-|max-|basis-|aspect-|size-)/.test(c)) return false;
    if (/^(p-|m-|px-|py-|pl-|pr-|pt-|pb-|mx-|my-|ml-|mr-|mt-|mb-|inset-|top-|right-|bottom-|left-)/.test(c)) return false;
    if (/^(text-|font-|leading-|tracking-|align-|whitespace-|break-|list-|decoration-|indent-|line-clamp-)/.test(c)) return false;
    if (/^(bg-|border-|rounded-|shadow-|ring-|divide-|outline-|opacity-|fill-|stroke-|accent-|caret-)/.test(c)) return false;
    if (/^(transition-|duration-|ease-|delay-|animate-|will-change-)/.test(c)) return false;
    if (/^(z-|scale-|rotate-|translate-|skew-|transform|origin-)/.test(c)) return false;
    if (/^(cursor-|select-|resize-|scroll-|snap-|touch-|pointer-|overscroll-)/.test(c)) return false;
    if (/^(object-|overflow-|float-|clear-)/.test(c)) return false;
    // Very generic structural names that appear everywhere
    if (/^(container|wrapper|inner|outer|wrap|content|section|main|header|footer|nav|sidebar|layout|page|app|root|body)$/.test(c)) return false;
    return true;
  }

  function absSelector(el, depth) {
    if (!el || el === document.documentElement) return 'html';
    if (el === document.body) return 'body';
    if ((depth || 0) > 8) return el.tagName.toLowerCase();
    var tag = el.tagName.toLowerCase();
    if (el.id && /^[a-zA-Z]/.test(el.id)) {
      try { if (document.querySelectorAll('#' + el.id).length === 1) return '#' + el.id; } catch(e) {}
    }
    var cls = Array.from(el.classList).filter(goodClass).slice(0, 2);
    var s = tag + (cls.length ? '.' + cls.join('.') : '');
    try { if (document.querySelectorAll(s).length === 1) return s; } catch(e) {}
    var par = el.parentElement;
    if (!par || par === document.body) return s;
    var sib = Array.from(par.children).filter(function(c) { return c.tagName === el.tagName; });
    if (sib.length > 1) s = tag + ':nth-of-type(' + (sib.indexOf(el) + 1) + ')';
    var ps = absSelector(par, (depth || 0) + 1);
    return (ps === 'body' || ps === 'html') ? s : ps + ' > ' + s;
  }

  function relSelector(el, base) {
    if (el === base) return null;
    var parts = []; var cur = el;
    while (cur && cur !== base && cur !== document.body) {
      var tag = cur.tagName.toLowerCase();
      var par = cur.parentElement;
      if (!par) break;
      var cls = Array.from(cur.classList).filter(goodClass).slice(0, 2);
      var s = tag + (cls.length ? '.' + cls.join('.') : '');
      var sib = Array.from(par.children).filter(function(c) { return c.tagName === cur.tagName; });
      if (sib.length > 1) s = tag + ':nth-of-type(' + (sib.indexOf(cur) + 1) + ')';
      parts.unshift(s);
      cur = par;
    }
    return parts.length ? parts.join(' > ') : null;
  }

  function detectContainer(el) {
    var cur = el.parentElement;
    while (cur && cur.parentElement && cur !== document.body) {
      var par = cur.parentElement;
      var sib = Array.from(par.children).filter(function(c) { return c.tagName === cur.tagName; });
      if (sib.length >= 2) return cur;
      cur = par;
    }
    return null;
  }

  function _selCount(s) {
    try { return document.querySelectorAll(s).length; } catch(e) { return 9999; }
  }

  function containerSelector(el) {
    var tag = el.tagName.toLowerCase();

    // 1. Prefer data-testid / data-component / data-block — highly specific
    var dataAttrs = ['data-testid','data-component','data-module','data-block','data-qa','data-id'];
    for (var di = 0; di < dataAttrs.length; di++) {
      var dv = el.getAttribute(dataAttrs[di]);
      if (!dv) continue;
      var ds = '[' + dataAttrs[di] + '="' + dv.replace(/"/g,'\\"') + '"]';
      var dc = _selCount(ds);
      if (dc >= 2 && dc <= 200) return ds;
    }

    // 2. Tag + good classes, increasing specificity until count is reasonable
    var allGood = Array.from(el.classList).filter(goodClass);
    var best = tag + (allGood.length ? '.' + allGood.slice(0,2).join('.') : '');
    var bestCount = _selCount(best);

    for (var k = 3; k <= allGood.length && bestCount > 50; k++) {
      var ext = tag + '.' + allGood.slice(0, k).join('.');
      var ec = _selCount(ext);
      if (ec >= 2) { best = ext; bestCount = ec; }
    }

    // 3. If still too broad, anchor to the nearest ancestor with a good selector
    if (bestCount > 50) {
      var cur = el.parentElement;
      var depth = 0;
      while (cur && cur !== document.body && depth < 4) {
        var parTag = cur.tagName.toLowerCase();

        // Check ancestor data attrs first
        for (var pdi = 0; pdi < dataAttrs.length; pdi++) {
          var pdv = cur.getAttribute(dataAttrs[pdi]);
          if (!pdv) continue;
          var pds = '[' + dataAttrs[pdi] + '="' + pdv.replace(/"/g,'\\"') + '"]';
          var candidate = pds + ' ' + best;
          var cc = _selCount(candidate);
          if (cc >= 2 && cc < bestCount) { best = candidate; bestCount = cc; }
        }

        // Ancestor id
        if (cur.id && /^[a-zA-Z]/.test(cur.id)) {
          var idSel = '#' + cur.id + ' ' + best;
          var ic = _selCount(idSel);
          if (ic >= 2 && ic < bestCount) { best = idSel; bestCount = ic; }
        }

        // Ancestor tag + good classes
        var parGood = Array.from(cur.classList).filter(goodClass).slice(0, 1);
        if (parGood.length) {
          var parSel = parTag + '.' + parGood[0];
          var childSel = parSel + ' > ' + tag + (allGood.length ? '.' + allGood.slice(0,2).join('.') : '');
          var xc = _selCount(childSel);
          if (xc >= 2 && xc < bestCount) { best = childSel; bestCount = xc; }
        }

        cur = cur.parentElement; depth++;
      }
    }

    return best;
  }

  function autoLink(base) {
    var links = Array.from(base.querySelectorAll('a[href]'));
    for (var i = 0; i < links.length; i++) {
      var href = links[i].getAttribute('href');
      if (href && href !== '#' && !/^(javascript:|mailto:|tel:)/.test(href)) {
        return relSelector(links[i], base) || 'a';
      }
    }
    return null;
  }

  function isIn(el, ancestor) {
    var c = el; while (c) { if (c === ancestor) return true; c = c.parentElement; } return false;
  }

  function getContainerHref(el) {
    var links = el.querySelectorAll('a[href]');
    for (var i = 0; i < links.length; i++) {
      var raw = links[i].getAttribute('href');
      if (!raw || raw === '#' || /^(javascript:|mailto:|tel:)/.test(raw)) continue;
      return links[i].href; // browser resolves to absolute URL via <base> tag
    }
    return null;
  }

  function looksLikeArticle(el) {
    if (el.children.length < 2) return false;
    var titleEl = el.querySelector('h1,h2,h3,h4,h5,h6');
    var titleTxt = titleEl ? (titleEl.textContent || '').replace(/\s+/g, ' ').trim() : '';
    if (!titleTxt) {
      var anchors = el.querySelectorAll('a');
      for (var i = 0; i < anchors.length; i++) {
        var t = (anchors[i].textContent || '').trim();
        if (t.length > 15) { titleTxt = t; break; }
      }
    }
    if (!titleTxt) return false;
    var pEl = el.querySelector('p');
    if (pEl && (pEl.textContent || '').replace(/\s+/g, ' ').trim().length >= 30) return true;
    var fullTxt = (el.textContent || '').replace(/\s+/g, ' ').trim();
    return fullTxt.replace(titleTxt, '').trim().length >= 50;
  }

  /* Highlight all container elements; excluded ones get red .__phx style */
  function markContainers() {
    document.querySelectorAll('.__phc,.__phx').forEach(function(e) {
      e.classList.remove('__phc', '__phx');
    });
    if (!containerBase) return 0;
    var included = 0;
    try {
      Array.from(document.querySelectorAll(containerBase)).forEach(function(e) {
        if (excludedEls.indexOf(e) < 0 && manuallyIncluded.indexOf(e) < 0 && !looksLikeArticle(e)) {
          excludedEls.push(e);
        }
        if (excludedEls.indexOf(e) >= 0) { e.classList.add('__phx'); }
        else { e.classList.add('__phc'); included++; }
      });
    } catch(e2) {}
    return included;
  }

  /* Highlight field elements (title, link, description, date, author) with green */
  function markFieldSelections() {
    document.querySelectorAll('.__phf').forEach(function(e) { e.classList.remove('__phf'); });
    if (!containerBase) return;
    var keys = ['selector_title', 'selector_link', 'selector_description', 'selector_date', 'selector_author'];
    try {
      Array.from(document.querySelectorAll(containerBase)).forEach(function(c) {
        keys.forEach(function(k) {
          if (!sel[k]) return;
          var el = c.querySelector(sel[k]);
          if (el) el.classList.add('__phf');
        });
      });
    } catch(e2) {}
  }

  /* Clear all restoration inline styles */
  function hideSelections() {
    _restoredEls.forEach(function(el) {
      el.style.removeProperty('outline');
      el.style.removeProperty('box-shadow');
      el.style.removeProperty('opacity');
      el.style.removeProperty('background-color');
    });
    _restoredEls = [];
    _highlightsShowing = false;
    var btn = document.getElementById('__tb_show');
    if (btn) btn.textContent = '◉ Previous Selections';
  }

  /* Apply saved selections as inline styles.
     Uses selector_item_excluded hrefs (new format) or falls back to old :not() CSS approach. */
  function showSelections() {
    hideSelections();
    var btn = document.getElementById('__tb_show');

    if (!containerBase) {
      if (btn) btn.textContent = '⚠ No saved selector';
      return;
    }

    var allContainers = [];
    try { allContainers = Array.from(document.querySelectorAll(containerBase)); } catch(e) {
      if (btn) btn.textContent = '⚠ Bad selector: ' + containerBase.slice(0, 30);
      return;
    }
    if (allContainers.length === 0) {
      if (btn) btn.textContent = '⚠ 0 found: ' + containerBase.slice(0, 40);
      return;
    }

    /* Choose exclusion strategy */
    var isExcluded;
    if (sel['selector_item_excluded'] !== undefined) {
      /* New format: excluded by href */
      var excHrefs = [];
      try { excHrefs = JSON.parse(sel['selector_item_excluded']); } catch(e) {}
      var excHrefSet = new Set(excHrefs);
      isExcluded = function(el) {
        var href = getContainerHref(el);
        return href !== null && excHrefSet.has(href);
      };
    } else if (_origContainerSel && _origContainerSel !== containerBase) {
      /* Old format: full :not() selector saved in DB before this fix */
      var incSet = new Set();
      try { Array.from(document.querySelectorAll(_origContainerSel)).forEach(function(el) { incSet.add(el); }); } catch(e) {}
      isExcluded = function(el) { return !incSet.has(el); };
    } else {
      isExcluded = function() { return false; };
    }

    container = allContainers[0];
    excludedEls = [];
    manuallyIncluded = [];
    var fieldKeys = ['selector_title', 'selector_link', 'selector_description', 'selector_date', 'selector_author'];

    allContainers.forEach(function(el) {
      var excl = isExcluded(el);
      if (excl) {
        excludedEls.push(el);
        el.style.setProperty('outline', '3px dashed #ef4444', 'important');
        el.style.setProperty('box-shadow', 'inset 0 0 0 3px rgba(239,68,68,0.3)', 'important');
        el.style.setProperty('opacity', '0.5', 'important');
      } else {
        manuallyIncluded.push(el);
        el.style.setProperty('outline', '3px dashed #8b5cf6', 'important');
        el.style.setProperty('box-shadow', 'inset 0 0 0 3px rgba(139,92,246,0.15)', 'important');
      }
      _restoredEls.push(el);

      if (!excl) {
        fieldKeys.forEach(function(k) {
          if (!sel[k]) return;
          try {
            var fEl = el.querySelector(sel[k]);
            if (fEl) {
              fEl.style.setProperty('outline', '2px solid #22c55e', 'important');
              fEl.style.setProperty('box-shadow', 'inset 0 0 0 2px rgba(34,197,94,0.25)', 'important');
              _restoredEls.push(fEl);
            }
          } catch(e2) {}
        });
      }
    });

    _highlightsShowing = true;
    if (btn) btn.textContent = '✕ Hide (' + manuallyIncluded.length + ' selected, ' + excludedEls.length + ' excluded)';
    refreshTb();
  }

  /* Recompute containerSel from base and broadcast to parent.
     Exclusions are now stored as link hrefs in selector_item_excluded, not as CSS :not() clauses.
     This ensures exclusions work consistently between the browser picker (JS-rendered DOM)
     and the Python extractor (raw HTML, no JS). */
  function updateContainerSel() {
    containerSel = containerBase;
    sel['selector_item'] = containerBase;
    var excludedHrefs = excludedEls.map(getContainerHref).filter(Boolean);
    // Deduplicate
    excludedHrefs = excludedHrefs.filter(function(h, i) { return excludedHrefs.indexOf(h) === i; });
    sel['selector_item_excluded'] = JSON.stringify(excludedHrefs);
    window.parent.postMessage({ type: 'rss-picker-field', field: 'selector_item', selector: containerBase }, '*');
    window.parent.postMessage({ type: 'rss-picker-field', field: 'selector_item_excluded', selector: JSON.stringify(excludedHrefs) }, '*');
    refreshTb();
  }

  function findContainerEl(el) {
    if (!containerBase) return null;
    var cur = el;
    while (cur && cur !== document.body) {
      try {
        if (Array.from(document.querySelectorAll(containerBase)).indexOf(cur) >= 0) return cur;
      } catch(e2) {}
      cur = cur.parentElement;
    }
    return null;
  }

  function assign(key, el) {
    if (key === 'selector_item') {
      container    = el;
      containerBase = containerSelector(el);
      containerSel  = containerBase;
      excludedEls   = [];
      manuallyIncluded = [];
      sel['selector_item'] = containerSel;
      var lnk = autoLink(el);
      if (lnk) sel['selector_link'] = lnk;
      markContainers();
      updateContainerSel();
      return;
    }
    if (!container) {
      var c = detectContainer(el);
      if (c) {
        container     = c;
        containerBase = containerSelector(c);
        containerSel  = containerBase;
        excludedEls   = [];
        manuallyIncluded = [];
        sel['selector_item'] = containerSel;
        var lnk2 = autoLink(c);
        if (lnk2) sel['selector_link'] = lnk2;
        markContainers();
        updateContainerSel();
      }
    }
    /* Find whichever container instance actually contains el.
       This handles multi-container selectors (e.g. 'li.a, li.b') and cases
       where container points to a different instance than the one clicked. */
    var activeContainer = container;
    if (containerBase) {
      try {
        var allC = Array.from(document.querySelectorAll(containerBase));
        for (var ci = 0; ci < allC.length; ci++) {
          if (isIn(el, allC[ci])) { activeContainer = allC[ci]; break; }
        }
      } catch(e2) {}
    }
    var s = null;
    if (activeContainer && isIn(el, activeContainer)) {
      s = relSelector(el, activeContainer);
      container = activeContainer; // keep active container in sync
    }
    if (!s) return;
    sel[key] = s;
    window.parent.postMessage({ type: 'rss-picker-field', field: key, selector: s }, '*');
    markFieldSelections();
    refreshTb();
  }

  /* ── Hover — capture-phase listener on document so it works regardless of
     the page's z-index stacking or pointer-events CSS ── */
  var hov = null, menu = null, menuX = 0, menuY = 0;

  document.addEventListener('mouseover', function(e) {
    if (menu) return;
    var el = e.target;
    if (!el || el === document.body || el === document.documentElement) return;
    if (el.closest && (el.closest('.__tb') || el.closest('.__pm'))) return;
    if (hov && hov !== el) hov.classList.remove('__ph');
    hov = el; hov.classList.add('__ph');
  }, true);

  document.addEventListener('mouseout', function(e) {
    if (menu) return;
    var el = e.target;
    if (el && el === hov && !e.relatedTarget) { hov.classList.remove('__ph'); hov = null; }
  }, true);

  /* ── Menu ── */
  function closeMenu() {
    if (menu) { menu.remove(); menu = null; }
    if (hov) { hov.classList.remove('__ph'); hov = null; }
  }

  function showMenu(el, x, y) {
    if (!el || el === document.body || el === document.documentElement) return;
    closeMenu();
    menuX = x; menuY = y; hov = el; el.classList.add('__ph');

    var tag = el.tagName.toLowerCase();
    var cls = Array.from(el.classList).filter(function(c) { return !/^__/.test(c); }).slice(0, 3).join(' ');
    var txt = (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 100);

    menu = document.createElement('div'); menu.className = '__pm';

    var info = document.createElement('div'); info.className = '__pm-info';
    info.textContent = '<' + tag + (cls ? ' .' + cls : '') + '>';
    menu.appendChild(info);

    if (txt) {
      var prev = document.createElement('div');
      prev.style.cssText = 'padding:0 10px 8px;font-size:11px;color:#374151;border-bottom:1px solid #f3f4f6;margin-bottom:4px;max-width:240px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;';
      prev.title = txt;
      prev.textContent = '\u201c' + txt + '\u201d';
      menu.appendChild(prev);
    }

    var nav = document.createElement('div');
    nav.style.cssText = 'display:flex;gap:4px;padding:0 6px 6px;';
    var hasPar = el.parentElement && el.parentElement !== document.body;
    var hasChild = el.children.length > 0;
    if (hasPar) {
      var up = document.createElement('button'); up.textContent = '↑ Parent';
      up.style.cssText = 'flex:1;font-size:11px;padding:4px;border:1px solid #e5e7eb;border-radius:4px;background:#f9fafb;cursor:pointer;';
      up.onclick = function(ev) { ev.stopPropagation(); showMenu(el.parentElement, menuX, menuY); };
      nav.appendChild(up);
    }
    if (hasChild) {
      var dn = document.createElement('button'); dn.textContent = '↓ Child';
      dn.style.cssText = 'flex:1;font-size:11px;padding:4px;border:1px solid #e5e7eb;border-radius:4px;background:#f9fafb;cursor:pointer;';
      dn.onclick = function(ev) { ev.stopPropagation(); showMenu(el.children[0], menuX, menuY); };
      nav.appendChild(dn);
    }
    if (hasPar || hasChild) menu.appendChild(nav);

    var sep0 = document.createElement('div'); sep0.className = '__pm-sep'; menu.appendChild(sep0);

    fields.forEach(function(f) {
      var row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:stretch;';

      var btn = document.createElement('button');
      btn.style.cssText = 'flex:1;text-align:left;';
      btn.textContent = f.icon + '  ' + f.label + (f.req ? '' : ' (optional)');
      if (sel[f.key]) btn.style.color = '#16a34a';
      btn.onclick = function(ev) {
        ev.stopPropagation();
        assign(f.key, el);
        closeMenu();
      };
      row.appendChild(btn);

      if (f.key !== 'selector_item' && sel[f.key]) {
        var clr = document.createElement('button');
        clr.title = 'Clear ' + f.label;
        clr.textContent = '✕';
        clr.style.cssText = 'padding:4px 8px;color:#9ca3af;border-left:1px solid #f3f4f6;flex-shrink:0;font-size:11px;';
        clr.onmouseenter = function() { clr.style.color = '#ef4444'; clr.style.background = '#fef2f2'; };
        clr.onmouseleave = function() { clr.style.color = '#9ca3af'; clr.style.background = ''; };
        clr.onclick = function(ev) {
          ev.stopPropagation();
          delete sel[f.key];
          window.parent.postMessage({ type: 'rss-picker-field', field: f.key, selector: '' }, '*');
          markFieldSelections();
          refreshTb();
          closeMenu();
        };
        row.appendChild(clr);
      }

      menu.appendChild(row);
    });

    if (container && containerBase) {
      var cEl = findContainerEl(el);
      if (cEl) {
        var isExcluded = excludedEls.indexOf(cEl) >= 0;
        var sepX = document.createElement('div'); sepX.className = '__pm-sep'; menu.appendChild(sepX);
        var excBtn = document.createElement('button');
        excBtn.textContent = isExcluded ? '✓  Include in feed' : '✕  Exclude from feed';
        excBtn.style.color  = isExcluded ? '#16a34a' : '#ef4444';
        excBtn.onclick = function(ev) {
          ev.stopPropagation();
          if (excludedEls.indexOf(cEl) >= 0) {
            excludedEls = excludedEls.filter(function(e) { return e !== cEl; });
            if (manuallyIncluded.indexOf(cEl) < 0) manuallyIncluded.push(cEl);
          } else {
            excludedEls.push(cEl);
          }
          markContainers();
          updateContainerSel();
          closeMenu();
        };
        menu.appendChild(excBtn);
      } else {
        /* Element is outside all current containers — offer to add it as an additional container type */
        var addSep = document.createElement('div'); addSep.className = '__pm-sep'; menu.appendChild(addSep);
        var addBtn = document.createElement('button');
        addBtn.textContent = '▦  Add to Container';
        addBtn.style.color = '#f97316';
        addBtn.onclick = function(ev) {
          ev.stopPropagation();
          var newSel = containerSelector(el);
          containerBase = containerBase + ', ' + newSel;
          /* Switch active container to the new element so subsequent field
             assignments (title, description, etc.) resolve relative to it */
          container = el;
          var lnk = autoLink(el);
          if (lnk) {
            sel['selector_link'] = lnk;
            window.parent.postMessage({ type: 'rss-picker-field', field: 'selector_link', selector: lnk }, '*');
          }
          markContainers();
          updateContainerSel();
          closeMenu();
        };
        menu.appendChild(addBtn);
      }
    }

    var sep = document.createElement('div'); sep.className = '__pm-sep'; menu.appendChild(sep);
    var cancel = document.createElement('button'); cancel.textContent = '✕  Cancel';
    cancel.style.color = '#9ca3af'; cancel.onclick = closeMenu;
    menu.appendChild(cancel);

    document.body.appendChild(menu);
    var mw = 240, mh = 280;
    var left = x + 12, top = y + 12;
    if (left + mw > window.innerWidth - 8) left = x - mw - 4;
    if (top + mh > window.innerHeight - 8) top = y - mh - 4;
    menu.style.left = Math.max(4, left) + 'px';
    menu.style.top  = Math.max(56, top) + 'px';
  }

  /* ── Click — capture phase so it fires before any page click handler ── */
  document.addEventListener('click', function(e) {
    var el = e.target;
    if (!el || el === document.body || el === document.documentElement) return;
    if (el.closest && (el.closest('.__tb') || el.closest('.__pm'))) return;
    e.preventDefault();
    e.stopPropagation();
    if (hov) { hov.classList.remove('__ph'); hov = null; }
    showMenu(el, e.clientX, e.clientY);
  }, true);

  document.addEventListener('keydown', function(e) { if (e.key === 'Escape') closeMenu(); });

  /* ── Load saved selectors injected by server (window.__RSS_INIT__) ── */
  (function() {
    var init = (typeof window.__RSS_INIT__ === 'object' && window.__RSS_INIT__) ? window.__RSS_INIT__ : null;
    if (!init || !init.selector_item) return;

    var keys = ['selector_item','selector_title','selector_link','selector_description','selector_date','selector_author','selector_item_excluded'];
    keys.forEach(function(k) { if (init[k] !== undefined) sel[k] = init[k]; });

    _origContainerSel = sel.selector_item; // save original before stripping (may have :not() from old saves)
    containerBase = sel.selector_item.replace(/:not\([^()]*(?:\([^()]*\)[^()]*)*\)/g, '').trim() || sel.selector_item;
    containerSel = containerBase;

    document.getElementById('__tb_show').style.display = '';
    showSelections();
    refreshTb();
  })();

  /* Keep accepting rss-picker-init messages too (future-proof fallback) */
  window.addEventListener('message', function(e) {
    if (!e.data || e.data.type !== 'rss-picker-init' || !e.data.selectors) return;
    var s = e.data.selectors;
    var keys = ['selector_item','selector_title','selector_link','selector_description','selector_date','selector_author','selector_item_excluded'];
    keys.forEach(function(k) { if (s[k] !== undefined) sel[k] = s[k]; });
    if (!sel.selector_item) return;
    _origContainerSel = sel.selector_item;
    containerBase = sel.selector_item.replace(/:not\([^()]*(?:\([^()]*\)[^()]*)*\)/g, '').trim() || sel.selector_item;
    containerSel = containerBase;
    document.getElementById('__tb_show').style.display = '';
    showSelections();
    refreshTb();
  });

  window.parent.postMessage({ type: 'rss-picker-ready' }, '*');

  /* ── Cookie / popup dismiss ──
     Tries common consent banner selectors, then falls back to button text matching.
     NOTE: cookie banners are usually position:fixed, so offsetParent is null —
     use getBoundingClientRect() for the visibility check instead. */
  function _isVisible(el) {
    try {
      var r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) return false;
      var cs = window.getComputedStyle(el);
      return cs.display !== 'none' && cs.visibility !== 'hidden' && cs.opacity !== '0';
    } catch(e) { return false; }
  }

  function dismissCookiePopup() {
    var candidates = [
      // OneTrust
      '#onetrust-accept-btn-handler',
      // CookieConsent.js (Insites)
      '.cc-accept', '.cc-btn.cc-allow', '.cc-btn.cc-dismiss',
      // Cookiebot
      '#CybotCookiebotDialogBodyButtonAccept',
      '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
      // Borlabs Cookie (WordPress)
      '#BorlabsCookieBtn--acceptAll',
      'button[data-borlabs-cookie-accept]',
      // Complianz (WordPress)
      '#cmplz-accept', '.cmplz-accept',
      // Cookie Notice & Compliance (WordPress)
      '#cn-accept-cookie', '.cn-set-cookie',
      // WP GDPR Cookie Consent
      '#wt-cli-accept-all-btn', '.wt-cli-accept-all-btn',
      // Cookie Law Info
      '#cookie_action_close_header',
      // GDPR Cookie Compliance
      '.cli-plugin-main-button', '.cli-accept',
      // Generic patterns
      '[aria-label*="accept" i]', '[aria-label*="agree" i]',
      'button[id*="accept-all" i]', 'button[id*="acceptAll" i]',
      'button[id*="agree" i]', 'button[id*="cookie" i]',
      'button[class*="accept-all" i]', 'button[class*="acceptAll" i]',
      'button[class*="agree" i]',
      'a[id*="accept" i]', 'a[class*="accept" i]',
      '[data-testid*="accept" i]', '[data-action*="accept" i]',
    ];
    for (var i = 0; i < candidates.length; i++) {
      try {
        var el = document.querySelector(candidates[i]);
        if (el && _isVisible(el)) { el.click(); return true; }
      } catch(e) {}
    }
    // Fallback: scan all visible buttons/links for accept-like text
    var btns = document.querySelectorAll('button, a[role="button"], input[type="button"], input[type="submit"]');
    var rx = /\b(accept all|accept cookies|accept everything|allow all|allow cookies|agree|i agree|ok|got it|confirm|continue)\b/i;
    for (var j = 0; j < btns.length; j++) {
      var b = btns[j];
      var t = (b.innerText || b.textContent || b.value || '').trim();
      if (rx.test(t) && _isVisible(b)) { b.click(); return true; }
    }
    return false;
  }

  /* ── Overlay / modal removal ──
     Hides any position:fixed or position:absolute element that covers a large
     portion of the viewport and has a high z-index.  This catches newsletter
     sign-up modals, lead-gen popups, and cookie banners that don't match the
     specific selectors above (e.g. lavender.ai, lemlist, etc.).
     Also unlocks body scroll in case the page froze it while the modal was open. */
  function removeOverlays() {
    var vpW = window.innerWidth  || document.documentElement.clientWidth  || 800;
    var vpH = window.innerHeight || document.documentElement.clientHeight || 600;
    var removed = 0;
    var all = document.querySelectorAll('*');
    for (var i = 0; i < all.length; i++) {
      var el = all[i];
      // Never touch our own toolbar/menu or the page skeleton
      if (!el || el === document.body || el === document.documentElement) continue;
      if (el.classList && (el.classList.contains('__tb') || el.classList.contains('__pm'))) continue;
      try {
        var cs = window.getComputedStyle(el);
        var pos = cs.position;
        if (pos !== 'fixed' && pos !== 'absolute') continue;
        var z = parseInt(cs.zIndex, 10);
        if (isNaN(z) || z < 10) continue;
        var r = el.getBoundingClientRect();
        // Must cover at least 40 % of both viewport dimensions
        if (r.width < vpW * 0.4 || r.height < vpH * 0.4) continue;
        // Skip scroll containers / layout wrappers that hold significant page content
        var innerTxt = (el.innerText || '').replace(/\s+/g, ' ').trim();
        if (innerTxt.length > 200) continue;
        el.style.setProperty('display', 'none', 'important');
        removed++;
      } catch(e) {}
    }
    // Re-enable scrolling that modals typically freeze
    try { document.body.style.setProperty('overflow', 'auto', 'important'); } catch(e) {}
    try { document.documentElement.style.setProperty('overflow', 'auto', 'important'); } catch(e) {}
    return removed;
  }

  /* Auto-dismiss on load: try cookie banners at 800 ms, then run the overlay
     sweeper at 1800 ms (after JS-driven modals have had time to appear). */
  setTimeout(dismissCookiePopup, 800);
  setTimeout(removeOverlays, 1800);

  window.addEventListener('message', function(e) {
    if (e.data && e.data.type === 'rss-picker-dismiss-popup') {
      var dismissed = dismissCookiePopup();
      // If no specific banner matched, nuke any large overlay covering the page
      if (!dismissed) removeOverlays();
      else removeOverlays();  // run it anyway — belt and braces
    }
  });

  /* ── Playwright detection ──
     Check at two points (1.5 s and 4 s) whether the page content looks sparse.
     The early check catches pure CSR apps that never hydrate; the late check
     catches SSR shells that pass the character threshold on skeleton/nav text
     but haven't finished fetching the real article list yet (e.g. Azure blog).
     Only fires when not already using Playwright. */
  function _checkNeedsPlaywright() {
    var spaRoot = document.getElementById('__next') ||
                  document.getElementById('__nuxt') ||
                  document.getElementById('root')   ||
                  document.getElementById('app');
    if (!spaRoot) return false;

    // Next.js App Router emits a <template data-dgst="BAILOUT_TO_CLIENT_SIDE_RENDERING">
    // inside any section whose content is delivered exclusively via the RSC payload.
    // Without the React runtime those sections render as empty placeholders — the
    // visual content the user wants to pick is simply not in the DOM.
    // Playwright is required so React can hydrate and materialise the real elements.
    if (document.querySelector('[data-dgst="BAILOUT_TO_CLIENT_SIDE_RENDERING"]')) return true;

    // Exclude our own toolbar text from the measurement
    var tb = document.querySelector('.__tb');
    if (tb) tb.style.visibility = 'hidden';
    var visibleText = (document.body.innerText || '').replace(/\s+/g, ' ').trim();
    if (tb) tb.style.visibility = '';
    return visibleText.length < 1200;
  }
  setTimeout(function() {
    if (_checkNeedsPlaywright()) {
      window.parent.postMessage({ type: 'rss-picker-needs-playwright' }, '*');
    }
  }, 1500);
  // Second pass: catches pages whose JS finishes late (lazy hydration, API-driven lists)
  setTimeout(function() {
    if (_checkNeedsPlaywright()) {
      window.parent.postMessage({ type: 'rss-picker-needs-playwright' }, '*');
    }
  }, 4000);

  /* If the server silently upgraded a Static request to Playwright (CSR bailout
     auto-detection), the page shows full content but the parent form still has
     use_playwright=false.  Signal the parent so it can flip the toggle and ensure
     the feed config is saved with use_playwright=true. */
  if (window.__RSS_USED_PLAYWRIGHT__) {
    window.parent.postMessage({ type: 'rss-picker-auto-playwright' }, '*');
  }
})();
</script>
"""


def _inject(html: str, base_url: str, init_selectors: dict | None = None, playwright_auto_used: bool = False) -> str:
    base_tag = f'<base href="{base_url}">\n'

    # Strip any X-Frame-Options / CSP meta tags
    html = re.sub(
        r'<meta[^>]+(?:x-frame-options|content-security-policy)[^>]*>',
        '',
        html,
        flags=re.IGNORECASE,
    )

    # Strip EXTERNAL <script src="..."> tags from the captured page.
    #
    # Why: SPA framework bundles (React, Next.js, Vue, etc.) are loaded via
    # external <script src> tags.  When the iframe re-runs them they trigger
    # re-hydration and fire data-fetch calls back to the origin.  Inside
    # sandbox="allow-scripts" the document origin is "null", so those calls
    # fail and many frameworks respond by replacing the rendered article list
    # with a loading/empty state.
    #
    # We keep INLINE <script> blocks intentionally.  They typically contain:
    #   • CSS-in-JS style injections (styled-components, Emotion, Stitches)
    #   • Theme/dark-mode class setup  (e.g. document.documentElement.className)
    #   • CSS custom-property definitions
    # Removing them strips the page of its visual styling, causing colour and
    # layout regressions (e.g. "all blue" on sites like lavender.ai).
    # Without the external bundles loaded, any inline React bootstrap code
    # will fail silently — ReactDOM is never defined — so re-hydration cannot
    # occur and the server-rendered DOM stays intact.
    html = re.sub(
        r'<script\b[^>]+\bsrc=["\'][^"\']*["\'][^>]*/?>(?:\s*</script>)?',
        '',
        html,
        flags=re.IGNORECASE,
    )

    # Strip Next.js App Router RSC (React Server Components) flight-data scripts.
    #
    # Why: Next.js 13+ App Router pages embed the RSC payload as thousands of
    # inline <script> calls: self.__next_f.push([1,"..."]) and
    # self.__next_s.push([...]).  On content-heavy pages (e.g. gong.io/blog)
    # these can total 10–15 MB, inflating the proxied HTML enormously and
    # making the iframe slow or unresponsive.  The payload is only consumed by
    # the Next.js client runtime — which we've already stripped — so removing
    # these scripts has no visual effect.  The server-rendered HTML nodes that
    # make the page visible are in the regular <div>/<article> tree, not here.
    html = re.sub(
        r'<script[^>]*>\s*(?:self\.__next_[a-zA-Z_]+=self\.__next_[a-zA-Z_]+\|\|\[\])?'
        r'\s*self\.__next_[a-zA-Z_]+\.push\([\s\S]*?</script>',
        '',
        html,
        flags=re.IGNORECASE,
    )

    # Replace Next.js CSR bailout sections with a visible placeholder.
    #
    # Next.js App Router wraps client-side-only components in a Suspense
    # boundary marked <!--$!-->...<!--/$-->.  When the component cannot be
    # rendered on the server it emits:
    #   <template data-dgst="BAILOUT_TO_CLIENT_SIDE_RENDERING"></template>
    #   <div class="min-h-screen"></div>          ← full-viewport empty block
    # Without the React runtime the section is entirely invisible to the user,
    # and the placeholder's min-h-screen class makes the whole iframe look blank.
    # We replace the entire boundary with a small informative banner so the user
    # knows they need Playwright rather than seeing a white void.
    _CSR_PLACEHOLDER = (
        '<div style="padding:0.6rem 1rem;margin:0.25rem 0;background:#1a2233;'
        'border-radius:6px;border:1px dashed #374151;color:#6b7280;'
        'font-family:system-ui,sans-serif;font-size:12px;text-align:center">'
        '&#9889; This section is dynamically rendered &mdash; enable '
        '<strong style="color:#f97316">Playwright</strong> in the toolbar to load it'
        '</div>'
    )
    html = re.sub(
        r'<!--\$!-->\s*<template[^>]+BAILOUT_TO_CLIENT_SIDE_RENDERING[^>]*>'
        r'</template>[\s\S]*?<!--/\$-->',
        _CSR_PLACEHOLDER,
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Navigation blocker — injected at the very top of <head> so it runs before
    # any inline page script (SPA routers, analytics, etc.).
    #
    # Problem: inline scripts kept for CSS-in-JS styling may include capture-phase
    # click listeners (e.g. Next.js router, GTM, Segment) that intercept any click
    # and navigate window.location to the href of the nearest <a> ancestor.  When
    # the user clicks an element in the picker, those listeners fire first and
    # redirect the iframe away from /api/picker to the real origin — which rejects
    # the direct iframe load (e.g. "lavender.ai refused to connect").
    #
    # Fix: install our own capture-phase listener and history overrides BEFORE any
    # page script so they win the "first listener wins" race.
    _NAV_BLOCKER = """\
<script>
(function(){
  /* 1. Kill SPA history-based navigation */
  try { history.pushState    = function(){}; } catch(e) {}
  try { history.replaceState = function(){}; } catch(e) {}

  /* 2. Block <a> navigation at capture phase.  Only preventDefault — no
     stopImmediatePropagation — so the picker's own capture listener still
     receives the click and can show the context menu. */
  document.addEventListener('click', function(e) {
    var n = e.target;
    while (n && n !== document) {
      if (n.tagName === 'A' && n.href) { e.preventDefault(); return; }
      n = n.parentNode;
    }
  }, true);

  /* 3. Block form submissions */
  document.addEventListener('submit', function(e) {
    e.preventDefault();
    e.stopImmediatePropagation();
  }, true);

  /* 4. Block window.open */
  try { window.open = function(){ return null; }; } catch(e) {}

  /* 5. Block dynamically-created external scripts (A/B testing, analytics CDNs).
     Inline scripts that call document.createElement('script') then set src to
     an external URL (e.g. Intellimize, Optimizely snippets) bypass our static
     <script src> stripping.  We intercept createElement so that any <script>
     element it returns has a no-op src setter for external URLs, and we also
     patch setAttribute on the returned element so setAttribute('src','https://...')
     is equally blocked.  This prevents A/B testing scripts from loading their
     CDN bundles, which avoids page-replacement side-effects and anti-flicker hangs. */
  (function() {
    var _dce = document.createElement.bind(document);
    document.createElement = function(tag) {
      var el = _dce.apply(this, arguments);
      if (typeof tag === 'string' && tag.toLowerCase() === 'script') {
        var _origSetAttr = el.setAttribute.bind(el);
        el.setAttribute = function(name, value) {
          if (name.toLowerCase() === 'src' && value && /^https?:/i.test(value)) return;
          _origSetAttr(name, value);
        };
        Object.defineProperty(el, 'src', {
          configurable: true,
          get: function() { return el.getAttribute('src') || ''; },
          set: function(v) { el.setAttribute('src', v); }
        });
      }
      return el;
    };
  })();
})();
</script>
"""

    # Inject <base> + nav-blocker (+ optional playwright flag) into <head>.
    _playwright_flag = '<script>window.__RSS_USED_PLAYWRIGHT__=true;</script>\n' if playwright_auto_used else ''
    for tag in ('<head>', '<Head>', '<HEAD>'):
        if tag in html:
            html = html.replace(tag, tag + '\n' + base_tag + _NAV_BLOCKER + _playwright_flag, 1)
            break

    # Build the script block to inject
    inject_block = ''
    if init_selectors:
        # json.dumps escapes all special chars; replace </ to prevent </script> injection
        safe_json = json.dumps(init_selectors).replace('</', '<\\/')
        inject_block += _INIT_SCRIPT.format(init_json=safe_json)
    inject_block += PICKER_SCRIPT

    # Inject just before </body> so document.body exists when it runs
    for tag in ('</body>', '</Body>', '</BODY>'):
        if tag in html:
            return html.replace(tag, inject_block + tag, 1)

    return html + inject_block


@router.get("/api/picker", response_class=HTMLResponse)
def picker_proxy(
    url: str = Query(..., description="Page URL to proxy for visual picking"),
    sel: str = Query(default="", description="JSON-encoded saved selectors to restore"),
    use_playwright: bool = Query(default=False, description="Use headless browser to render JS before picking"),
    wait_seconds: int = Query(default=0, ge=0, le=120, description="Extra seconds to wait after page load (Dynamic mode)"),
):
    """Fetch a page and inject the RSS visual selector picker script."""
    playwright_auto_used = False
    try:
        result = fetch_page(url, use_playwright=use_playwright, wait_seconds=wait_seconds)
        # Auto-upgrade to Playwright when the static fetch returns a Next.js
        # CSR bailout section and Playwright is available.  We track this so the
        # injected page can signal the parent frame to flip use_playwright=true,
        # ensuring the saved feed config also uses Playwright for scraping.
        if (
            not use_playwright
            and settings.playwright_enabled
            and 'BAILOUT_TO_CLIENT_SIDE_RENDERING' in result.html
        ):
            try:
                result = fetch_page(url, use_playwright=True, wait_seconds=wait_seconds)
                playwright_auto_used = True
            except Exception:
                pass  # fall back to the original static result
    except Exception as exc:
        # Return an HTML error page so the iframe shows a readable message
        # instead of a blank white box (which happens when a JSON 502 is loaded).
        safe_url = url.replace("<", "&lt;").replace(">", "&gt;")
        safe_err = str(exc).replace("<", "&lt;").replace(">", "&gt;")
        error_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;font-family:system-ui,sans-serif;background:#111827;color:#f3f4f6;padding:2rem">
  <h2 style="color:#f87171;margin-top:0">&#9888; Could not load page</h2>
  <p style="color:#9ca3af;word-break:break-all">{safe_url}</p>
  <pre style="background:#1f2937;padding:1rem;border-radius:6px;color:#fca5a5;
              font-size:12px;white-space:pre-wrap;word-break:break-all">{safe_err}</pre>
  <p style="color:#6b7280;font-size:13px;line-height:1.6">
    <strong style="color:#d1d5db">Possible causes:</strong><br>
    &bull; The site uses Cloudflare or aggressive bot protection &mdash;
      try opening the URL in a normal browser tab first to solve any CAPTCHA,
      then retry here.<br>
    &bull; The page requires JavaScript &mdash; make sure
      <strong style="color:#d1d5db">Playwright</strong> is enabled.<br>
    &bull; Network timeout &mdash; the site may be slow or unreachable.
  </p>
</body></html>"""
        return HTMLResponse(content=error_html, status_code=200)

    init_selectors: dict | None = None
    if sel:
        try:
            init_selectors = json.loads(sel)
        except Exception:
            pass

    html = _inject(result.html, result.final_url, init_selectors, playwright_auto_used=playwright_auto_used)
    return HTMLResponse(content=html, headers={"X-Frame-Options": "SAMEORIGIN"})
