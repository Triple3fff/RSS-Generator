import re
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import HTMLResponse

from ..scraper.fetcher import fetch_page

router = APIRouter(tags=["picker"])

PICKER_SCRIPT = r"""
<style id="__rss_picker_style">
  html { margin-top: 52px !important; }
  .__ph  { outline: 2px solid #f97316 !important; background: rgba(249,115,22,0.07) !important; }
  .__phc { outline: 2px dashed #8b5cf6 !important; background: rgba(139,92,246,0.04) !important; }
  .__phx { outline: 2px dashed #ef4444 !important; background: rgba(239,68,68,0.06) !important; opacity: 0.55; }
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
  .__tb-title { font-weight: 700; color: #f97316; font-size: 13px; white-space: nowrap; }
  .__tb-hint  { color: #9ca3af; font-size: 11px; flex: 1; }
  .__tb-fields { display: flex; gap: 6px; flex-wrap: wrap; }
  .__tb-f { font-size: 11px; }
  .__tb-f.done { color: #4ade80; }
  .__tb-f.auto { color: #60a5fa; }
  .__tb-f.pend { color: #6b7280; }
  .__tb-apply  { padding: 4px 10px; background: #f97316; border: none; border-radius: 5px; color: #fff; cursor: pointer; font-weight: 600; font-size: 12px; white-space: nowrap; }
  .__tb-cancel { padding: 4px 8px; background: #374151; border: 1px solid #4b5563; border-radius: 5px; color: #fff; cursor: pointer; font-size: 12px; }
  #__rss_ov { position: fixed; top: 52px; left: 0; right: 0; bottom: 0; z-index: 2147483645; cursor: crosshair; }
</style>
<script id="__rss_picker_script">
(function() {
  /* ── State ── */
  var sel = {};             // collected selectors
  var container    = null;  // detected repeating item container DOM element
  var containerSel = '';    // effective CSS selector (may include :not() exclusions)
  var containerBase = '';   // base selector without :not() clauses
  var excludedEls  = [];    // container DOM elements the user has manually deselected

  var fields = [
    { key: 'selector_item',        label: 'Item Container', icon: '▦',  req: true  },
    { key: 'selector_title',       label: 'Title',          icon: 'T',  req: true  },
    { key: 'selector_description', label: 'Description',    icon: '¶',  req: false },
    { key: 'selector_date',        label: 'Date',           icon: '⏰', req: false },
    { key: 'selector_author',      label: 'Author',         icon: '👤', req: false },
  ];

  /* ── Toolbar ── */
  var tb = document.createElement('div'); tb.className = '__tb';
  tb.innerHTML =
    '<span class="__tb-title">RSS Picker</span>' +
    '<span class="__tb-hint" id="__tb_hint">Click any article title to start</span>' +
    '<div class="__tb-fields" id="__tb_f"></div>' +
    '<button class="__tb-apply" id="__tb_ok">Apply</button>' +
    '<button class="__tb-cancel" id="__tb_x">Cancel</button>';
  document.body.appendChild(tb);

  function refreshTb() {
    var hint = document.getElementById('__tb_hint');
    var fc   = document.getElementById('__tb_f');
    if (!container) {
      hint.textContent = 'Click an article element and assign it as Item Container or Title';
      fc.innerHTML = '';
      return;
    }
    var cnt = 0;
    try { cnt = document.querySelectorAll(containerSel).length; } catch(e) {}
    hint.textContent = '▦ ' + containerSel + ' (' + cnt + ' articles)' + (sel.selector_link ? '  🔗 auto' : '');
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

  /* Restore selectors from parent when picker re-opens with existing config */
  window.addEventListener('message', function(e) {
    if (!e.data || e.data.type !== 'rss-picker-init' || !e.data.selectors) return;
    var s = e.data.selectors;
    var keys = ['selector_item','selector_title','selector_link','selector_description','selector_date','selector_author'];
    keys.forEach(function(k) { if (s[k]) sel[k] = s[k]; });
    if (sel.selector_item) {
      containerSel  = sel.selector_item;
      /* Recover base by stripping any :not(...) exclusion clauses */
      containerBase = containerSel.replace(/:not\([^)]*\)/g, '').trim() || containerSel;
      excludedEls   = [];  // can't recover DOM refs from stored CSS, start fresh
      try {
        var els = document.querySelectorAll(containerBase);
        if (els.length > 0) { container = els[0]; markContainers(); }
      } catch(e2) {}
    }
    refreshTb();
  });

  /* ── Overlay ── */
  var ov = document.createElement('div'); ov.id = '__rss_ov';
  document.body.appendChild(ov);

  /* ── Utilities ── */
  function goodClass(c) {
    return c.length > 1 &&
      !/^(active|hover|focus|open|visible|hidden|show|selected|current|first|last|odd|even|disabled|loading)$/.test(c) &&
      !/^(is-|has-|js-)/.test(c) && !/\d{3,}/.test(c);
  }

  /* Absolute selector from document root */
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

  /* Relative selector from base (item container) to el */
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

  /* Walk up from el to find the first ancestor that repeats in its parent (≥2 same-tag siblings) */
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

  /*
   * Generate a GENERAL selector for the item container — one that matches ALL
   * similar article elements, not just the one clicked.
   * Unlike absSelector, we never add :nth-of-type here.
   */
  function containerSelector(el) {
    var tag = el.tagName.toLowerCase();
    var cls = Array.from(el.classList).filter(goodClass).slice(0, 2);
    var sel = tag + (cls.length ? '.' + cls.join('.') : '');

    // If this already matches our element on the page, use it as-is.
    // Matching multiple elements is exactly what we want for a container selector.
    try {
      var matches = Array.from(document.querySelectorAll(sel));
      if (matches.indexOf(el) >= 0) return sel;
    } catch(e) {}

    // Need one level of parent context to distinguish from other elements.
    var par = el.parentElement;
    if (!par || par === document.body) return sel;

    var parTag = par.tagName.toLowerCase();
    var parCls = Array.from(par.classList).filter(goodClass).slice(0, 1);
    var parSel = parTag + (parCls.length ? '.' + parCls[0] : '');
    return parSel + ' > ' + sel;
  }

  /* Auto-detect link: first <a href> in container, returns relative selector */
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

  /* isDescendant check */
  function isIn(el, ancestor) {
    var c = el; while (c) { if (c === ancestor) return true; c = c.parentElement; } return false;
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
        if (excludedEls.indexOf(e) >= 0) { e.classList.add('__phx'); }
        else { e.classList.add('__phc'); included++; }
      });
    } catch(e2) {}
    return included;
  }

  /* Recompute containerSel from base + current exclusions and broadcast to parent */
  function updateContainerSel() {
    if (excludedEls.length === 0) {
      containerSel = containerBase;
    } else {
      var nths = excludedEls.map(function(el) {
        var par = el.parentElement;
        if (!par) return -1;
        var sibs = Array.from(par.children).filter(function(c) { return c.tagName === el.tagName; });
        return sibs.indexOf(el) + 1;   // 1-indexed :nth-of-type
      }).filter(function(n) { return n > 0; });
      // deduplicate
      var seen = {};
      nths = nths.filter(function(n) { return seen[n] ? false : (seen[n] = true); });
      containerSel = containerBase + nths.map(function(n) {
        return ':not(:nth-of-type(' + n + '))';
      }).join('');
    }
    sel['selector_item'] = containerSel;
    window.parent.postMessage({ type: 'rss-picker-field', field: 'selector_item', selector: containerSel }, '*');
    refreshTb();
  }

  /* Walk up from el to find the nearest ancestor (or self) that is a container element */
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

  /* Assign a field: auto-detect container on first assignment, generate relative selector */
  function assign(key, el) {
    if (key === 'selector_item') {
      /* Manual container selection — generate a general selector matching ALL similar items */
      container    = el;
      containerBase = containerSelector(el);
      containerSel  = containerBase;
      excludedEls   = [];
      sel['selector_item'] = containerSel;
      var lnk = autoLink(el);
      if (lnk) sel['selector_link'] = lnk;
      markContainers();
      window.parent.postMessage({ type: 'rss-picker-field', field: key, selector: containerSel }, '*');
      refreshTb();
      return;
    }

    /* For other fields: auto-detect container if not yet known */
    if (!container) {
      var c = detectContainer(el);
      if (c) {
        container     = c;
        containerBase = containerSelector(c);
        containerSel  = containerBase;
        excludedEls   = [];
        sel['selector_item'] = containerSel;
        var lnk2 = autoLink(c);
        if (lnk2) sel['selector_link'] = lnk2;
        markContainers();
      }
    }

    var s = (container && isIn(el, container))
            ? (relSelector(el, container) || absSelector(el))
            : absSelector(el);
    sel[key] = s;
    window.parent.postMessage({ type: 'rss-picker-field', field: key, selector: s }, '*');
    refreshTb();
  }

  /* ── Smallest element at point ── */
  function elAt(x, y) {
    ov.style.pointerEvents = 'none';
    var all = document.elementsFromPoint ? document.elementsFromPoint(x, y) : [document.elementFromPoint(x, y)];
    ov.style.pointerEvents = 'auto';

    var best = null, bestA = Infinity;
    for (var i = 0; i < all.length; i++) {
      var c = all[i];
      if (!c || c === ov || c === document.body || c === document.documentElement) continue;
      if (c.closest && (c.closest('.__tb') || c.closest('.__pm'))) continue;
      var r = c.getBoundingClientRect();
      var a = r.width * r.height;
      if (a > 0 && a < bestA) { bestA = a; best = c; }
    }

    /* elementsFromPoint misses elements whose pointer-events are blocked by an ancestor
       (e.g. a full-card <a> link sitting on top of a <p> description inside it).
       Scan ALL descendants of best by bounding-box to find smaller elements at the point. */
    if (best) {
      var rootR = best.getBoundingClientRect();
      bestA = rootR.width * rootR.height;
      var descendants = best.querySelectorAll('*');
      for (var j = 0; j < descendants.length; j++) {
        var bc = descendants[j];
        if (bc === ov) continue;
        if (bc.closest && (bc.closest('.__tb') || bc.closest('.__pm'))) continue;
        var cr = bc.getBoundingClientRect();
        if (cr.width > 0 && cr.height > 0 &&
            x >= cr.left && x <= cr.right && y >= cr.top && y <= cr.bottom) {
          var ca = cr.width * cr.height;
          if (ca < bestA) { bestA = ca; best = bc; }
        }
      }
    }

    return best;
  }

  /* ── Hover ── */
  var hov = null, menu = null, menuX = 0, menuY = 0;

  ov.addEventListener('mousemove', function(e) {
    if (menu) return;
    var el = elAt(e.clientX, e.clientY);
    if (!el) return;
    if (hov && hov !== el) hov.classList.remove('__ph');
    hov = el; hov.classList.add('__ph');
  });
  ov.addEventListener('mouseleave', function() {
    if (hov) { hov.classList.remove('__ph'); hov = null; }
  });

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
    var cls = Array.from(el.classList).slice(0, 3).join(' ');
    var txt = (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 100);

    menu = document.createElement('div'); menu.className = '__pm';

    /* Tag info */
    var info = document.createElement('div'); info.className = '__pm-info';
    info.textContent = '<' + tag + (cls ? ' .' + cls : '') + '>';
    menu.appendChild(info);

    /* Text preview */
    if (txt) {
      var prev = document.createElement('div');
      prev.style.cssText = 'padding:0 10px 8px;font-size:11px;color:#374151;border-bottom:1px solid #f3f4f6;margin-bottom:4px;max-width:240px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;';
      prev.title = txt;
      prev.textContent = '\u201c' + txt + '\u201d';
      menu.appendChild(prev);
    }

    /* Navigate */
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
      var btn = document.createElement('button');
      btn.textContent = f.icon + '  ' + f.label + (f.req ? '' : ' (optional)');
      if (sel[f.key]) btn.style.color = '#16a34a';
      btn.onclick = function(ev) {
        ev.stopPropagation();
        assign(f.key, el);
        closeMenu();
      };
      menu.appendChild(btn);
    });

    /* Exclude / Include this container */
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
          } else {
            excludedEls.push(cEl);
          }
          markContainers();
          updateContainerSel();
          closeMenu();
        };
        menu.appendChild(excBtn);
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

  ov.addEventListener('click', function(e) {
    var el = elAt(e.clientX, e.clientY);
    if (el) showMenu(el, e.clientX, e.clientY);
  });

  document.addEventListener('keydown', function(e) { if (e.key === 'Escape') closeMenu(); });
})();
</script>
"""


def _inject(html: str, base_url: str) -> str:
    base_tag = f'<base href="{base_url}">\n'

    # Strip any X-Frame-Options / CSP meta tags
    html = re.sub(
        r'<meta[^>]+(?:x-frame-options|content-security-policy)[^>]*>',
        '',
        html,
        flags=re.IGNORECASE,
    )

    # Inject <base> into <head> so assets resolve correctly
    for tag in ('<head>', '<Head>', '<HEAD>'):
        if tag in html:
            html = html.replace(tag, tag + '\n' + base_tag, 1)
            break

    # Inject picker script just before </body> so document.body exists when it runs
    for tag in ('</body>', '</Body>', '</BODY>'):
        if tag in html:
            return html.replace(tag, PICKER_SCRIPT + tag, 1)

    return html + PICKER_SCRIPT


@router.get("/api/picker", response_class=HTMLResponse)
def picker_proxy(url: str = Query(..., description="Page URL to proxy for visual picking")):
    """Fetch a page and inject the RSS visual selector picker script."""
    try:
        result = fetch_page(url, use_playwright=False)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not fetch page: {exc}")

    html = _inject(result.html, result.final_url)
    return HTMLResponse(content=html, headers={"X-Frame-Options": "SAMEORIGIN"})
