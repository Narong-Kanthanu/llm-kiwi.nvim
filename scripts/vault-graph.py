#!/usr/bin/env python3
"""
vault-graph.py — LLM Kiwi knowledge graph generator

Scans [[wikilinks]] across one or more vaults and renders an interactive
vis.js force-directed graph (single-file HTML). Designed to be launched
from Neovim via the llm-kiwi.nvim plugin; vaults are always passed
explicitly on the command line.

Usage:
    python3 vault-graph.py --vault notes=~/notes
    python3 vault-graph.py --vault personal=~/notes --vault work=~/work-notes --all
    python3 vault-graph.py --vault notes=~/notes --output ~/graph.html --no-open

    # Server mode (launched from Neovim for open-in-nvim):
    python3 vault-graph.py --vault notes=~/notes --nvim-server /tmp/nvimXXX/0
"""

import argparse
import http.server
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.parse
import webbrowser
from collections import defaultdict
from pathlib import Path

SERVER_PORT = 18765
PID_FILE = Path("/tmp/llm-kiwi-server.pid")


# ── Parse arguments ──────────────────────────────────────────────────────────

def _parse_vault(s: str) -> tuple[str, Path]:
    if "=" not in s:
        raise argparse.ArgumentTypeError(f"--vault expects NAME=PATH, got: {s!r}")
    name, _, raw_path = s.partition("=")
    name = name.strip()
    if not name:
        raise argparse.ArgumentTypeError(f"--vault name is empty: {s!r}")
    path = Path(raw_path.strip()).expanduser().resolve()
    return name, path


DEFAULT_CHROMIUM_APPS = [
    "Google Chrome",
    "Google Chrome Canary",
    "Brave Browser",
    "Microsoft Edge",
    "Vivaldi",
    "Chromium",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Generate LLM Kiwi knowledge graph")
    parser.add_argument("--vault", dest="vaults", action="append", default=[],
                        type=_parse_vault,
                        help="Add a vault: NAME=PATH (repeatable)")
    parser.add_argument("--all", action="store_true",
                        help="Include all --vault entries with in-browser selector (default when >1)")
    parser.add_argument("--active", help="Default active vault name when multiple are configured")
    parser.add_argument("--output", help="Output HTML file path (default: common root of vaults)")
    parser.add_argument("--no-open", action="store_true", help="Don't open browser")
    parser.add_argument("--nvim-server", help="Neovim server address (enables HTTP server with open-in-nvim)")
    parser.add_argument("--chromium-app", dest="chromium_apps", action="append",
                        default=None,
                        help="macOS Chromium app name to try for open/refresh (repeatable)")
    args = parser.parse_args()
    if not args.chromium_apps:
        args.chromium_apps = list(DEFAULT_CHROMIUM_APPS)
    return args


# ── Scan vault ────────────────────────────────────────────────────────────────

WIKILINK_RE = re.compile(r'\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]')

def get_folder_group(path: Path, vault_root: Path) -> str:
    """Return top-level folder name for color coding."""
    try:
        relative = path.relative_to(vault_root)
        parts = relative.parts
        if len(parts) > 1:
            return parts[0]
        return "root"
    except ValueError:
        return "root"

def scan_vault(vault_root: Path):
    """Scan all .md files, extract wikilinks, build nodes + edges."""
    vault_root = vault_root.resolve()
    md_files = list(vault_root.rglob("*.md"))

    # Build a name → path map for resolving wikilinks
    name_to_path = {}
    for f in md_files:
        stem = f.stem.lower()
        if stem not in name_to_path:
            name_to_path[stem] = f

    nodes = {}
    links_raw = []

    for f in md_files:
        rel = str(f.relative_to(vault_root))
        node_id = rel
        group = get_folder_group(f, vault_root)

        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            content = ""

        # Count words roughly
        word_count = len(content.split())

        # Extract wikilinks
        wikilinks = WIKILINK_RE.findall(content)

        nodes[node_id] = {
            "id": node_id,
            "label": f.stem,
            "group": group,
            "words": word_count,
            "path": str(f),
            "links_out": len(wikilinks),
        }

        for target_name in wikilinks:
            target_key = target_name.strip().lower()
            # Try to resolve to a real file
            resolved = name_to_path.get(target_key)
            if resolved:
                target_id = str(resolved.relative_to(vault_root))
            else:
                # Unresolved link — still show as a ghost node
                target_id = f"__unresolved__/{target_name.strip()}"
                if target_id not in nodes:
                    nodes[target_id] = {
                        "id": target_id,
                        "label": target_name.strip(),
                        "group": "unresolved",
                        "words": 0,
                        "path": "",
                        "links_out": 0,
                    }

            if node_id != target_id:
                links_raw.append({"source": node_id, "target": target_id})

    # Deduplicate links
    seen = set()
    links = []
    for l in links_raw:
        key = (l["source"], l["target"])
        if key not in seen:
            seen.add(key)
            links.append(l)

    # Count backlinks
    backlink_count = defaultdict(int)
    for l in links:
        backlink_count[l["target"]] += 1
    for nid, node in nodes.items():
        node["links_in"] = backlink_count.get(nid, 0)

    return list(nodes.values()), links


# ── HTML template ─────────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LLM Kiwi — Knowledge Graph</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #1a2332; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; overflow: hidden; display: flex; height: 100vh; }
  #network-container { width: 100%; height: 100%; }
  #graph-wrap { position: relative; flex: 1; min-width: 0; height: 100%; }
  .vis-network:focus, .vis-network canvas:focus { outline: none; }

  /* Tooltip */
  #tooltip {
    position: absolute;
    background: #152030;
    border: 1px solid #3a5a6a44;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 12px;
    color: #a0b8c8;
    pointer-events: none;
    opacity: 0;
    transition: opacity .15s;
    max-width: 220px;
    z-index: 10;
  }
  #tooltip .title { font-size: 13px; font-weight: 600; color: #cdd3da; margin-bottom: 4px; }
  #tooltip .meta { color: #79a8eb; font-size: 11px; }

  /* Controls */
  #controls {
    position: relative;
    flex: 0 0 232px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-height: 0;
  }
  #controls > select, #controls > input, #controls > button, #controls > #explorer {
    box-sizing: border-box;
    width: 100%;
  }
  #workspace-select, #search-box {
    background: #152030;
    border: 1px solid #3a5a6a44;
    border-radius: 8px;
    padding: 7px 12px;
    color: #cdd3da;
    font-size: 13px;
    outline: none;
  }
  #workspace-select { cursor: pointer; }
  #workspace-select:focus, #search-box:focus { border-color: #79a8eb; }
  #search-box::placeholder { color: #4a6a7a; }

  /* Explorer */
  #explorer {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    background: #15203088;
    border: 1px solid #3a5a6a22;
    border-radius: 8px;
    overflow: hidden;
  }
  #explorer-header {
    color: #a0b8c8;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 10px 12px 6px 12px;
  }
  #explorer-list {
    flex: 1;
    overflow-y: auto;
    padding: 2px 0 8px 0;
    font-size: 12px;
    font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif;
    outline: none;
  }
  #explorer-list:focus { box-shadow: none; }
  #explorer-list::-webkit-scrollbar { width: 6px; }
  #explorer-list::-webkit-scrollbar-track { background: transparent; }
  #explorer-list::-webkit-scrollbar-thumb { background: #3a5a6a44; border-radius: 3px; }
  .explorer-row {
    padding: 3px 8px 3px 8px;
    color: #cdd3da;
    cursor: pointer;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    user-select: none;
  }
  .explorer-row.folder { color: #a0b8c8; }
  .explorer-row:hover { background: #1e304055; }
  .explorer-row.selected { background: #1e3040; color: #79a8eb; }
  .explorer-empty { padding: 8px 12px; color: #4a6a7a; font-size: 11px; font-style: italic; }

  /* Stats */
  #stats {
    margin-top: auto;
    color: #4a6a7a;
    font-size: 11px;
    font-family: monospace;
    line-height: 1.8;
  }

  /* Confirm modal */
  #confirm-overlay {
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(10, 15, 25, 0.7);
    z-index: 100;
    align-items: center;
    justify-content: center;
  }
  #confirm-overlay.active { display: flex; }
  #confirm-box {
    background: #152030;
    border: 1px solid #3a5a6a;
    border-radius: 12px;
    padding: 24px 32px;
    max-width: 420px;
    text-align: center;
  }
  #confirm-box .msg { color: #cdd3da; font-size: 14px; margin-bottom: 6px; }
  #confirm-box .sub { color: #4a6a7a; font-size: 12px; margin-bottom: 20px; }
  #confirm-box .btns { display: flex; gap: 12px; justify-content: center; }
  #confirm-box button {
    padding: 8px 24px;
    border-radius: 8px;
    border: 1px solid #3a5a6a44;
    font-size: 13px;
    cursor: pointer;
    transition: background .15s;
  }
  #confirm-box .btn-cancel { background: #1e3040; color: #79a8eb; }
  #confirm-box .btn-cancel:hover { background: #253a50; }
  #confirm-box .btn-open { background: #79a8eb; color: #0d1520; font-weight: 600; border-color: #79a8eb; }
  #confirm-box .btn-open:hover { background: #5a90d0; }

  /* Keymap help */
  #keymap-help {
    position: absolute;
    bottom: 50px;
    right: 16px;
    background: #15203088;
    border: 1px solid #3a5a6a22;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 11px;
    font-family: monospace;
    color: #4a6a7a;
    line-height: 1.7;
    z-index: 5;
    display: none;
  }
  #keymap-help .key { color: #79a8eb; font-weight: 600; display: inline-block; min-width: 60px; }
  #keymap-help .desc { color: #4a6a7a; }

  /* Legend */
  #legend {
    position: absolute;
    top: 16px;
    right: 16px;
    background: #152030;
    border: 1px solid #3a5a6a22;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 11px;
    color: #79a8eb;
    min-width: 130px;
    z-index: 5;
  }
  #legend .legend-title { color: #a0b8c8; font-size: 12px; margin-bottom: 8px; font-weight: 600; }
  .legend-item { display: flex; align-items: center; gap: 7px; margin-bottom: 5px; }
  .legend-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }

  /* Hint */
  #hint {
    position: absolute;
    bottom: 16px;
    right: 16px;
    color: #2a3a4a;
    font-size: 11px;
    text-align: right;
    line-height: 1.8;
    z-index: 5;
  }

  /* Reset button */
  #reset-btn {
    background: #152030;
    border: 1px solid #3a5a6a44;
    border-radius: 8px;
    padding: 6px 12px;
    color: #79a8eb;
    font-size: 12px;
    cursor: pointer;
    transition: background .15s;
  }
  #reset-btn:hover { background: #1e3040; }

</style>
</head>
<body>

<div id="controls">
  <select id="workspace-select"></select>
  <input id="search-box" type="text" placeholder="Search notes..." />
  <div id="explorer">
    <div id="explorer-header">Explorer</div>
    <div id="explorer-list" tabindex="0"></div>
  </div>
  <button id="reset-btn" onclick="resetView()">Reset view</button>
  <div id="stats"></div>
</div>

<div id="graph-wrap">
  <div id="network-container"></div>
  <div id="legend">
    <div class="legend-title">Folders</div>
    <div id="legend-items"></div>
  </div>
  <div id="keymap-help"></div>
  <div id="hint">drag · scroll to zoom · hover to highlight · click to focus</div>
</div>

<div id="tooltip"><div class="title"></div><div class="meta"></div></div>
<div id="confirm-overlay">
  <div id="confirm-box">
    <div class="msg"></div>
    <div class="sub"></div>
    <div class="btns">
      <button class="btn-cancel">[n] Cancel</button>
      <button class="btn-open">[y] Open</button>
    </div>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<script>
const WORKSPACES_DATA = __WORKSPACES_DATA__;
const ACTIVE_WORKSPACE = "__ACTIVE_WORKSPACE__";

// ── Color palette (Obsidian-style: yellow-green, teal, blue tones) ────────
const PALETTE = [
  '#c8d84e', '#4ecdc4', '#79a8eb', '#a882ff',
  '#e8d44d', '#56c1b3', '#6bb5e0', '#d4a0e0',
  '#8ecf65', '#45b7d1',
];

// ── State ─────────────────────────────────────────────────────────────────
let network = null;
let nodesDS = null;
let edgesDS = null;
let GROUP_COLORS = {};
let focusedNode = null;
let searchActive = false;
let savedSearchQuery = '';
let clickTimer = null;
let selectedNode = null;
const container = document.getElementById('network-container');
const IS_SERVER_MODE = location.protocol === 'http:' || location.protocol === 'https:';

// ── vis.js options ────────────────────────────────────────────────────────
const options = {
  physics: {
    solver: 'barnesHut',
    barnesHut: {
      gravitationalConstant: -2500,
      centralGravity: 0.3,
      springLength: 95,
      springConstant: 0.04,
      damping: 0.09,
      avoidOverlap: 0.1,
    },
    stabilization: { iterations: 150 },
  },
  interaction: {
    hover: true,
    tooltipDelay: 100,
    dragNodes: true,
    dragView: true,
    zoomView: true,
    zoomSpeed: 0.6,
  },
  nodes: {
    shape: 'dot',
    borderWidth: 0,
    shadow: { enabled: true, size: 12, x: 0, y: 0 },
    font: { face: '-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif' },
  },
  edges: {
    smooth: false,
    color: { inherit: false },
    width: 0.5,
  },
};

// ── Node size helper ──────────────────────────────────────────────────────
function nodeSize(n) {
  const total = (n.links_in || 0) + (n.links_out || 0);
  if (n.group === 'unresolved') return 2;
  return 3 + Math.min(total * 0.8, 8);
}

// ── Build workspace selector ──────────────────────────────────────────────
const wsSelect = document.getElementById('workspace-select');
const wsNames = Object.keys(WORKSPACES_DATA);

wsNames.forEach(name => {
  const opt = document.createElement('option');
  opt.value = name;
  opt.textContent = name.charAt(0).toUpperCase() + name.slice(1);
  if (name === ACTIVE_WORKSPACE) opt.selected = true;
  wsSelect.appendChild(opt);
});

wsSelect.addEventListener('change', () => renderGraph(wsSelect.value));

// ── Render graph ──────────────────────────────────────────────────────────
function renderGraph(wsName) {
  if (network) { network.destroy(); network = null; }
  selectedNode = null;
  focusedNode = null;
  searchActive = false;
  savedSearchQuery = '';
  document.getElementById('search-box').value = '';
  document.getElementById('tooltip').style.opacity = 0;

  const data = WORKSPACES_DATA[wsName];

  // ── Explorer (file tree) ─────────────────────────────────────────────
  // Rendered BEFORE vis.js initialization so it still appears even if the
  // graph canvas fails to initialize (e.g. CDN blocked, sandboxed browser).
  const explorerList = document.getElementById('explorer-list');
  let explorerTree = buildExplorerTree(data.nodes);
  let explorerVisible = flattenExplorer(explorerTree);
  let explorerIndex = -1;

  function buildExplorerTree(nodes) {
    const root = { name: '', type: 'folder', children: [], expanded: true, depth: 0 };
    for (const n of nodes) {
      if (!n.path || n.group === 'unresolved') continue;
      const parts = n.id.split('/');
      let cur = root;
      for (let i = 0; i < parts.length - 1; i++) {
        const name = parts[i];
        let child = cur.children.find(c => c.type === 'folder' && c.name === name);
        if (!child) {
          child = { name, type: 'folder', children: [], expanded: true, depth: cur.depth + 1 };
          cur.children.push(child);
        }
        cur = child;
      }
      cur.children.push({
        name: parts[parts.length - 1],
        type: 'file',
        nodeId: n.id,
        path: n.path,
        depth: cur.depth + 1,
      });
    }
    sortTree(root);
    return root;
  }

  function sortTree(node) {
    if (!node.children) return;
    node.children.sort((a, b) => {
      if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    node.children.forEach(sortTree);
  }

  function flattenExplorer(root) {
    const out = [];
    function walk(n) {
      if (n !== root) out.push(n);
      if (n.type === 'folder' && n.expanded) n.children.forEach(walk);
    }
    walk(root);
    return out;
  }

  function renderExplorerList() {
    explorerList.innerHTML = '';
    if (!explorerVisible.length) {
      const empty = document.createElement('div');
      empty.className = 'explorer-empty';
      empty.textContent = 'no notes';
      explorerList.appendChild(empty);
      return;
    }
    explorerVisible.forEach((row, i) => {
      const el = document.createElement('div');
      el.className = 'explorer-row ' + row.type;
      el.style.paddingLeft = (8 + (row.depth - 1) * 12) + 'px';
      if (i === explorerIndex) el.classList.add('selected');
      const icon = row.type === 'folder' ? (row.expanded ? '\u25be ' : '\u25b8 ') : '\u2022 ';
      const label = row.type === 'file' ? row.name.replace(/\.md$/, '') : row.name;
      el.textContent = icon + label;
      el.title = label;
      el.addEventListener('click', () => {
        if (row.type === 'folder') {
          row.expanded = !row.expanded;
          explorerVisible = flattenExplorer(explorerTree);
          renderExplorerList();
        } else {
          explorerSelect(i, true, true);
          if (IS_SERVER_MODE) openInNvim(row.path);
        }
      });
      explorerList.appendChild(el);
    });
  }

  function explorerSelect(i, point, pan) {
    if (point === undefined) point = true;
    if (pan === undefined) pan = false;
    if (i < 0 || i >= explorerVisible.length) return;
    explorerIndex = i;
    const children = explorerList.children;
    for (let k = 0; k < children.length; k++) {
      children[k].classList.toggle('selected', k === i);
    }
    const el = children[i];
    if (el && el.scrollIntoView) el.scrollIntoView({ block: 'nearest' });
    const row = explorerVisible[i];
    if (point && row.type === 'file' && row.nodeId && typeof selectNode === 'function' && nodesDS) {
      try { selectNode(row.nodeId, { pan }); } catch (err) { /* graph not ready */ }
    }
  }

  function explorerMove(delta) {
    if (!explorerVisible.length) return;
    let i = explorerIndex;
    if (i < 0) i = delta > 0 ? 0 : explorerVisible.length - 1;
    else i = Math.max(0, Math.min(explorerVisible.length - 1, i + delta));
    explorerSelect(i, true, true);
  }

  function explorerToggle(expand) {
    const row = explorerVisible[explorerIndex];
    if (!row || row.type !== 'folder') return false;
    if (expand === true) row.expanded = true;
    else if (expand === false) row.expanded = false;
    else row.expanded = !row.expanded;
    explorerVisible = flattenExplorer(explorerTree);
    renderExplorerList();
    return true;
  }

  function enterExplorer() {
    explorerList.focus();
    // Pan on entry so the picked node is guaranteed on-screen; j/k keep pan=false to avoid queued animations.
    if (explorerIndex < 0) {
      const firstFile = explorerVisible.findIndex(r => r.type === 'file');
      if (firstFile >= 0) explorerSelect(firstFile, true, true);
      else if (explorerVisible.length) explorerSelect(0, false);
    } else {
      explorerSelect(explorerIndex, true, true);
    }
  }

  function exitExplorer() {
    explorerList.blur();
    // Match exit symmetry with focus/search: clear any highlight the tree left on the graph.
    if (selectedNode) selectNode(null);
    tip.style.opacity = 0;
  }

  renderExplorerList();

  // Build color map
  GROUP_COLORS = {};
  const groups = [...new Set(data.nodes.map(n => n.group))].filter(g => g !== 'unresolved');
  groups.forEach((g, i) => { GROUP_COLORS[g] = PALETTE[i % PALETTE.length]; });
  GROUP_COLORS['unresolved'] = '#2a3a4a';

  // Legend
  const legendEl = document.getElementById('legend-items');
  legendEl.innerHTML = '';
  groups.forEach(grp => {
    const item = document.createElement('div');
    item.className = 'legend-item';
    item.innerHTML = '<div class="legend-dot" style="background:' + GROUP_COLORS[grp] + '"></div><span>' + grp + '</span>';
    legendEl.appendChild(item);
  });
  const unresolvedItem = document.createElement('div');
  unresolvedItem.className = 'legend-item';
  unresolvedItem.innerHTML = '<div class="legend-dot" style="background:#2a3a4a;border:1px solid #4a6a7a"></div><span style="color:#4a6a7a">unresolved</span>';
  legendEl.appendChild(unresolvedItem);

  // Stats
  const realNodes = data.nodes.filter(n => n.group !== 'unresolved');
  document.getElementById('stats').innerHTML = wsName + '<br>' + realNodes.length + ' notes &nbsp;&middot;&nbsp; ' + data.links.length + ' links';

  // Build vis.js datasets
  const visNodes = data.nodes.map(n => {
    const total = (n.links_in || 0) + (n.links_out || 0);
    const color = GROUP_COLORS[n.group] || '#4a6a7a';
    const isUnresolved = n.group === 'unresolved';
    return {
      id: n.id,
      label: total >= 3 ? n.label : undefined,
      size: nodeSize(n),
      color: {
        background: color,
        border: color,
        highlight: { background: '#ffffff', border: '#ffffff' },
        hover: { background: '#ffffff', border: '#ffffff' },
      },
      opacity: isUnresolved ? 0.25 : 0.9,
      shadow: { enabled: !isUnresolved, color: color + '80', size: 8 + Math.min(total * 2, 16), x: 0, y: 0 },
      font: {
        color: '#cdd3da',
        size: total > 4 ? 11 : 9,
        strokeWidth: 2,
        strokeColor: '#1a2332',
        vadjust: -(nodeSize(n) + 4),
      },
      // Metadata for hover/search/open
      _label: n.label,
      _group: n.group,
      _color: color,
      _links_in: n.links_in || 0,
      _links_out: n.links_out || 0,
      _words: n.words || 0,
      _total: total,
      _path: n.path || '',
    };
  });

  const visEdges = data.links.map((l, i) => ({
    id: 'e' + i,
    from: l.source,
    to: l.target,
    color: { color: '#3a5a63', opacity: 0.35 },
    width: 0.5,
  }));

  nodesDS = new vis.DataSet(visNodes);
  edgesDS = new vis.DataSet(visEdges);

  network = new vis.Network(container, { nodes: nodesDS, edges: edgesDS }, options);

  // ── Hover highlight ──────────────────────────────────────────────────
  const tip = document.getElementById('tooltip');

  function defaultNodeStyle(n) {
    return { id: n.id, opacity: n._group === 'unresolved' ? 0.25 : 0.9, label: n._total >= 3 ? n._label : undefined };
  }
  function defaultEdgeStyle(e) {
    return { id: e.id, color: { color: '#3a5a63', opacity: 0.35 }, width: 0.5 };
  }
  function restoreFocusStyle() {
    nodesDS.update(nodesDS.get().filter(n => !n.hidden).map(n => ({ id: n.id, opacity: 1 })));
    edgesDS.update(edgesDS.get().filter(e => !e.hidden).map(e => ({ id: e.id, color: { color: '#79a8eb', opacity: 0.7 }, width: 1.5 })));
  }

  function resetHover() {
    tip.style.opacity = 0;
    nodesDS.update(nodesDS.get().map(defaultNodeStyle));
    edgesDS.update(edgesDS.get().map(defaultEdgeStyle));
  }

  network.on('hoverNode', function(params) {
    if (searchActive) return;
    const nodeId = params.node;
    const nd = nodesDS.get(nodeId);
    if (nd._group === 'unresolved') return;

    // Show tooltip in any mode
    tip.querySelector('.title').textContent = nd._label;
    tip.querySelector('.meta').innerHTML =
      nd._group + ' &nbsp;&middot;&nbsp; ' + nd._links_in + ' &larr; &nbsp; ' + nd._links_out + ' &rarr;' +
      (nd._words > 0 ? '<br>' + nd._words + ' words' : '');
    tip.style.opacity = 1;

    if (focusedNode) {
      // Focus-mode hover: highlight hovered node's connections within visible subgraph
      const hoverConn = new Set([nodeId, ...network.getConnectedNodes(nodeId)]);
      const hoverEdges = new Set(network.getConnectedEdges(nodeId));

      nodesDS.update(nodesDS.get().filter(n => !n.hidden).map(n => ({
        id: n.id,
        opacity: hoverConn.has(n.id) ? 1 : 0.3,
      })));

      edgesDS.update(edgesDS.get().filter(e => !e.hidden).map(e => ({
        id: e.id,
        color: { color: '#79a8eb', opacity: hoverEdges.has(e.id) ? 0.9 : 0.15 },
        width: hoverEdges.has(e.id) ? 2 : 0.5,
      })));
      return;
    }

    // Normal mode hover
    const connNodes = new Set([nodeId, ...network.getConnectedNodes(nodeId)]);
    const connEdges = new Set(network.getConnectedEdges(nodeId));

    nodesDS.update(nodesDS.get().map(n => ({
      id: n.id,
      opacity: connNodes.has(n.id) ? 1 : 0.08,
      label: connNodes.has(n.id) ? n._label : undefined,
    })));

    edgesDS.update(edgesDS.get().map(e => ({
      id: e.id,
      color: { color: connEdges.has(e.id) ? '#79a8eb' : '#3a5a6a', opacity: connEdges.has(e.id) ? 0.8 : 0.03 },
      width: connEdges.has(e.id) ? 1.5 : 0.3,
    })));
  });

  network.on('blurNode', function() {
    if (searchActive) return;
    tip.style.opacity = 0;
    if (focusedNode) { restoreFocusStyle(); return; }
    nodesDS.update(nodesDS.get().map(defaultNodeStyle));
    edgesDS.update(edgesDS.get().map(defaultEdgeStyle));
  });

  // Position tooltip via mouse
  if (window._mouseMoveHandler) container.removeEventListener('mousemove', window._mouseMoveHandler);
  window._mouseMoveHandler = function(e) {
    tip.style.right = 'auto';
    tip.style.left = (e.pageX + 14) + 'px';
    tip.style.top = (e.pageY - 32) + 'px';
  };
  container.addEventListener('mousemove', window._mouseMoveHandler);

  // ── Search ───────────────────────────────────────────────────────────
  const searchBox = document.getElementById('search-box');
  searchBox.value = '';
  const newSearch = searchBox.cloneNode(true);
  searchBox.parentNode.replaceChild(newSearch, searchBox);

  function applySearch(q) {
    // Find matched nodes and all their connected neighbors
    const directMatched = nodesDS.get().filter(n => n._label.toLowerCase().includes(q));
    const matchedIds = new Set(directMatched.map(n => n.id));
    const visibleNodes = new Set(matchedIds);
    const visibleEdges = new Set();

    matchedIds.forEach(id => {
      network.getConnectedNodes(id).forEach(nid => visibleNodes.add(nid));
      network.getConnectedEdges(id).forEach(eid => visibleEdges.add(eid));
    });

    // Hide non-related, show matched + connections with labels
    nodesDS.update(nodesDS.get().map(n => ({
      id: n.id,
      hidden: !visibleNodes.has(n.id),
      opacity: matchedIds.has(n.id) ? 1 : (visibleNodes.has(n.id) ? 0.6 : 0),
      label: visibleNodes.has(n.id) ? n._label : undefined,
      font: visibleNodes.has(n.id) ? {
        color: matchedIds.has(n.id) ? '#ffffff' : '#cdd3da',
        size: matchedIds.has(n.id) ? 13 : 11,
        strokeWidth: 2, strokeColor: '#1a2332',
        vadjust: -(nodeSize(n) + 4),
      } : n.font,
    })));

    edgesDS.update(edgesDS.get().map(e => ({
      id: e.id,
      hidden: !visibleEdges.has(e.id),
      color: { color: '#79a8eb', opacity: visibleEdges.has(e.id) ? 0.6 : 0 },
      width: visibleEdges.has(e.id) ? 1.2 : 0,
    })));

    // Zoom to fit visible nodes
    if (visibleNodes.size > 0) {
      network.fit({
        nodes: [...visibleNodes],
        animation: { duration: 400, easingFunction: 'easeInOutQuad' },
      });
    }
  }

  function restoreNormal() {
    searchActive = false;
    savedSearchQuery = '';
    newSearch.value = '';
    tip.style.opacity = 0;
    nodesDS.update(nodesDS.get().map(n => ({
      ...defaultNodeStyle(n),
      hidden: false,
      font: { color: '#cdd3da', size: n._total > 4 ? 11 : 9, strokeWidth: 2, strokeColor: '#1a2332', vadjust: -(nodeSize(n) + 4) },
    })));
    edgesDS.update(edgesDS.get().map(e => ({ ...defaultEdgeStyle(e), hidden: false })));
    network.fit({ animation: { duration: 500, easingFunction: 'easeInOutQuad' } });
  }

  newSearch.addEventListener('input', function() {
    const q = this.value.trim().toLowerCase();
    if (!q) {
      restoreNormal();
      return;
    }
    resetHover();
    searchActive = true;
    savedSearchQuery = q;
    applySearch(q);
  });

  newSearch.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') { e.preventDefault(); newSearch.blur(); }
    if (e.key === 'Escape') { e.preventDefault(); newSearch.blur(); restoreNormal(); }
  });

  // ── Focus mode (click node to zoom, click background to exit) ────────
  function enterFocus(nodeId) {
    focusedNode = nodeId;
    const nd = nodesDS.get(nodeId);
    if (!nd || nd._group === 'unresolved') return;

    const connNodes = new Set([nodeId, ...network.getConnectedNodes(nodeId)]);
    const connEdges = new Set(network.getConnectedEdges(nodeId));

    // Show connected nodes with labels, hide the rest
    nodesDS.update(nodesDS.get().map(n => {
      const visible = connNodes.has(n.id);
      return {
        id: n.id,
        hidden: !visible,
        label: visible ? n._label : undefined,
        opacity: visible ? 1 : 0,
        font: visible ? { color: '#cdd3da', size: n.id === nodeId ? 14 : 12, strokeWidth: 2, strokeColor: '#1a2332' } : n.font,
      };
    }));

    edgesDS.update(edgesDS.get().map(e => ({
      id: e.id,
      hidden: !connEdges.has(e.id),
      color: { color: '#79a8eb', opacity: connEdges.has(e.id) ? 0.7 : 0 },
      width: connEdges.has(e.id) ? 1.5 : 0,
    })));

    // Zoom to fit the connected subgraph
    network.fit({
      nodes: [...connNodes],
      animation: { duration: 500, easingFunction: 'easeInOutQuad' },
    });

  }

  function exitFocus() {
    if (!focusedNode) return;
    focusedNode = null;
    selectNode(null);

    // If search was active before focus, return to search results
    if (savedSearchQuery) {
      searchActive = true;
      applySearch(savedSearchQuery);
      return;
    }

    // Otherwise restore normal mode
    restoreNormal();
  }

  // ── Vim navigation (hjkl + Enter) ──────────────────────────────────
  const origSizes = new Map();

  function selectNode(nodeId, opts) {
    const pan = !opts || opts.pan !== false;
    // Restore previous node
    if (selectedNode) {
      const origSize = origSizes.get(selectedNode);
      const prev = nodesDS.get(selectedNode);
      if (prev) nodesDS.update({
        id: selectedNode,
        borderWidth: 0,
        size: origSize != null ? origSize : prev.size,
        shadow: { enabled: prev._group !== 'unresolved', color: (prev._color || '#4ecdc4') + '80', size: 8, x: 0, y: 0 },
      });
    }
    selectedNode = nodeId;
    if (!nodeId) { tip.style.opacity = 0; return; }

    const nd = nodesDS.get(nodeId);
    if (!origSizes.has(nodeId)) origSizes.set(nodeId, nd.size);
    const baseSize = origSizes.get(nodeId);

    // Highlight: red border + enlarged + glow
    nodesDS.update({
      id: nodeId,
      borderWidth: 3,
      size: baseSize * 1.8,
      color: { ...nd.color, border: '#ff4444' },
      shadow: { enabled: true, color: '#ff444488', size: 25, x: 0, y: 0 },
    });

    // Show tooltip under Folders legend (top-right)
    tip.querySelector('.title').textContent = nd._label;
    tip.querySelector('.meta').innerHTML =
      (nd._group || '') + ' &nbsp;&middot;&nbsp; ' + (nd._links_in || 0) + ' &larr; &nbsp; ' + (nd._links_out || 0) + ' &rarr;' +
      (nd._words > 0 ? '<br>' + nd._words + ' words' : '');
    const legendRect = document.getElementById('legend').getBoundingClientRect();
    tip.style.right = '16px';
    tip.style.left = 'auto';
    tip.style.top = (legendRect.bottom + 8) + 'px';
    tip.style.opacity = 1;

    // Smooth pan. vis.js cancels the prior animation on each call, so rapid presses from hjkl or explorer j/k retarget instead of queuing.
    if (pan) {
      const pos = network.getPositions([nodeId])[nodeId];
      network.moveTo({ position: pos, scale: network.getScale(), animation: { duration: 400, easingFunction: 'easeInOutCubic' } });
    }
  }

  function navigateVim(direction) {
    const allNodes = nodesDS.get().filter(n => !n.hidden);
    if (!allNodes.length) return;

    if (!selectedNode) {
      const center = network.getViewPosition();
      let best = null, bestDist = Infinity;
      allNodes.forEach(n => {
        const pos = network.getPositions([n.id])[n.id];
        const d = Math.hypot(pos.x - center.x, pos.y - center.y);
        if (d < bestDist) { bestDist = d; best = n.id; }
      });
      selectNode(best);
      return;
    }

    const curPos = network.getPositions([selectedNode])[selectedNode];
    if (!curPos) return;
    const connected = new Set(network.getConnectedNodes(selectedNode));
    let best = null, bestScore = Infinity;

    allNodes.forEach(n => {
      if (n.id === selectedNode) return;
      const pos = network.getPositions([n.id])[n.id];
      const dx = pos.x - curPos.x;
      const dy = pos.y - curPos.y;
      let valid = false;
      if (direction === 'h') valid = dx < 0 && Math.abs(dx) > Math.abs(dy) * 0.3;
      if (direction === 'l') valid = dx > 0 && Math.abs(dx) > Math.abs(dy) * 0.3;
      if (direction === 'j') valid = dy > 0 && Math.abs(dy) > Math.abs(dx) * 0.3;
      if (direction === 'k') valid = dy < 0 && Math.abs(dy) > Math.abs(dx) * 0.3;
      if (!valid) return;
      const d = Math.hypot(dx, dy);
      const score = connected.has(n.id) ? d * 0.5 : d;
      if (score < bestScore) { bestScore = score; best = n.id; }
    });

    if (best) selectNode(best);
  }

  // ── Open-in-nvim helpers ─────────────────────────────────────────────
  function resolveFilePath(nd) {
    if (nd._path) return nd._path;
    // Unresolved node: find matching resolved node by ID
    const target = nd.id.replace('__unresolved__/', '');
    const match = nodesDS.get().find(n =>
      n._path && (n.id.endsWith(target + '.md') || n.id.endsWith(target))
    );
    if (match) return match._path;
    // Fallback: construct from vault_path + label
    const vaultPath = (WORKSPACES_DATA[wsSelect.value] || {}).vault_path;
    if (vaultPath && nd._label) {
      return vaultPath + '/' + nd._label.replace(/\.md$/, '') + '.md';
    }
    return null;
  }

  const confirmOverlay = document.getElementById('confirm-overlay');
  const confirmBox = document.getElementById('confirm-box');

  function showConfirm(msg, sub, onOpen) {
    confirmBox.querySelector('.msg').textContent = msg;
    confirmBox.querySelector('.sub').textContent = sub;
    confirmOverlay.classList.add('active');
    const btnOpen = confirmBox.querySelector('.btn-open');
    const btnCancel = confirmBox.querySelector('.btn-cancel');
    function cleanup() {
      confirmOverlay.classList.remove('active');
      btnOpen.replaceWith(btnOpen.cloneNode(true));
      btnCancel.replaceWith(btnCancel.cloneNode(true));
      document.removeEventListener('keydown', onKey);
    }
    function onKey(e) {
      if (e.key === 'y') { e.preventDefault(); cleanup(); onOpen(); }
      if (e.key === 'n' || e.key === 'Escape') { e.preventDefault(); cleanup(); }
    }
    document.addEventListener('keydown', onKey);
    btnOpen.addEventListener('click', () => { cleanup(); onOpen(); });
    btnCancel.addEventListener('click', cleanup);
  }

  function openInNvim(filePath) {
    const vaultPath = (WORKSPACES_DATA[wsSelect.value] || {}).vault_path;
    fetch('/api/cwd').then(r => r.json()).then(data => {
      const cwd = data.cwd || '';
      if (!vaultPath || cwd.startsWith(vaultPath) || vaultPath.startsWith(cwd)) {
        fetch('/api/open?path=' + encodeURIComponent(filePath)).catch(() => {});
      } else {
        // Outside vault — try tmux first, fall back to confirm modal
        fetch('/api/open-in-tmux?path=' + encodeURIComponent(filePath) + '&vault=' + encodeURIComponent(vaultPath))
          .then(r => r.json()).then(res => {
            if (!res.tmux) {
              const name = filePath.split('/').pop();
              showConfirm('Open ' + name + '?',
                'Neovim is outside your vault (' + cwd.split('/').pop() + ')',
                () => fetch('/api/open?path=' + encodeURIComponent(filePath)).catch(() => {}));
            }
          }).catch(() => {
            fetch('/api/open?path=' + encodeURIComponent(filePath)).catch(() => {});
          });
      }
    }).catch(() => {
      fetch('/api/open?path=' + encodeURIComponent(filePath)).catch(() => {});
    });
  }

  function findNearestNode(canvasPos) {
    let best = null, bestDist = Infinity;
    nodesDS.get().forEach(n => {
      const pos = network.getPositions([n.id])[n.id];
      const d = Math.hypot(canvasPos.x - pos.x, canvasPos.y - pos.y);
      if (d < bestDist) { bestDist = d; best = n; }
    });
    return bestDist < 80 ? best : null;
  }

  // ── Click ────────────────────────────────────────────────────────────
  // Dot click:   single → focus, double → open file
  // Label click: single → open file
  // Empty click: exit focus / restore
  network.on('click', function(params) {
    if (params.nodes.length > 0) {
      const nodeId = params.nodes[0];
      const nd = nodesDS.get(nodeId);

      // Label click → open file immediately
      if (IS_SERVER_MODE && nd) {
        const pos = network.getPositions([nodeId])[nodeId];
        const canvas = params.pointer.canvas;
        const dist = Math.hypot(canvas.x - pos.x, canvas.y - pos.y);
        if (dist > (nd.size || 5)) {
          if (clickTimer) { clearTimeout(clickTimer); clickTimer = null; }
          const filePath = resolveFilePath(nd);
          if (filePath) openInNvim(filePath);
          return;
        }
      }

      // Dot click → focus mode
      if (IS_SERVER_MODE) {
        if (clickTimer) { clearTimeout(clickTimer); clickTimer = null; }
        clickTimer = setTimeout(() => {
          clickTimer = null;
          searchActive = false;
          enterFocus(nodeId);
        }, 250);
      } else {
        searchActive = false;
        enterFocus(nodeId);
      }
    } else {
      if (IS_SERVER_MODE) {
        const nd = findNearestNode(params.pointer.canvas);
        if (nd) {
          const filePath = resolveFilePath(nd);
          if (filePath) { openInNvim(filePath); return; }
        }
      }
      if (focusedNode) exitFocus();
      else if (searchActive) restoreNormal();
    }
  });

  // Double-click: open file in nvim
  network.on('doubleClick', function(params) {
    if (!IS_SERVER_MODE) return;
    if (clickTimer) { clearTimeout(clickTimer); clickTimer = null; }
    const nd = params.nodes.length > 0
      ? nodesDS.get(params.nodes[0])
      : findNearestNode(params.pointer.canvas);
    if (!nd) return;
    const filePath = resolveFilePath(nd);
    if (filePath) openInNvim(filePath);
  });

  document.getElementById('hint').textContent =
    'e explorer \u00b7 f search \u00b7 hjkl navigate \u00b7 enter focus \u00b7 o open \u00b7 esc back';
  const keymapEl = document.getElementById('keymap-help');
  keymapEl.innerHTML = [
    ['h j k l', 'navigate'],
    ['e', 'explorer'],
    ['f', 'search'],
    ['w', 'workspace (j/k pick)'],
    ['enter', 'focus node'],
    ['o', 'open in nvim'],
    ['y / n', 'confirm / cancel'],
    ['esc', 'go back'],
  ].map(([k, d]) => '<div><span class="key">' + k + '</span><span class="desc">' + d + '</span></div>').join('');
  keymapEl.style.display = 'block';

  // Remove previous keydown handler before adding new one
  if (window._graphKeyHandler) document.removeEventListener('keydown', window._graphKeyHandler);
  window._graphKeyHandler = function(e) {
    if (e.key === 'Escape') {
      if (document.activeElement === wsSelect) {
        e.preventDefault();
        if (wsSelect._prevValue) wsSelect.value = wsSelect._prevValue;
        wsSelect.blur();
        return;
      }
      if (document.activeElement === explorerList) {
        e.preventDefault();
        exitExplorer();
        return;
      }
      if (focusedNode) exitFocus();
      else if (selectedNode) selectNode(null);
      else if (searchActive) restoreNormal();
      else resetView();
      return;
    }
    // Explorer focused: vim-style tree nav, open file, toggle folders
    if (document.activeElement === explorerList) {
      if (e.key === 'j') { e.preventDefault(); explorerMove(1); return; }
      if (e.key === 'k') { e.preventDefault(); explorerMove(-1); return; }
      if (e.key === 'l') {
        const row = explorerVisible[explorerIndex];
        if (row && row.type === 'folder') { e.preventDefault(); explorerToggle(true); }
        return;
      }
      if (e.key === 'h') {
        const row = explorerVisible[explorerIndex];
        if (row && row.type === 'folder' && row.expanded) {
          e.preventDefault();
          explorerToggle(false);
        }
        return;
      }
      if (e.key === 'Enter') {
        const row = explorerVisible[explorerIndex];
        if (!row) return;
        e.preventDefault();
        if (row.type === 'folder') explorerToggle();
        else if (IS_SERVER_MODE) openInNvim(row.path);
        return;
      }
      if (e.key === 'o') {
        const row = explorerVisible[explorerIndex];
        if (row && row.type === 'file' && IS_SERVER_MODE) {
          e.preventDefault();
          openInNvim(row.path);
        }
        return;
      }
      return;
    }
    // Input mode: disable vim navigation, handle only input-specific keys
    if (document.activeElement === newSearch || document.activeElement === wsSelect) {
      if (document.activeElement === wsSelect) {
        if (e.key === 'j' || e.key === 'k') {
          e.preventDefault();
          const idx = wsSelect.selectedIndex;
          if (e.key === 'j' && idx < wsSelect.options.length - 1) wsSelect.selectedIndex = idx + 1;
          if (e.key === 'k' && idx > 0) wsSelect.selectedIndex = idx - 1;
        }
        if (e.key === 'Enter') {
          e.preventDefault();
          wsSelect.blur();
          renderGraph(wsSelect.value);
        }
      }
      return;
    }
    if (e.key === 'e') {
      e.preventDefault();
      enterExplorer();
      return;
    }
    if (e.key === 'f') {
      e.preventDefault();
      newSearch.focus();
      newSearch.select();
      return;
    }
    if (e.key === 'w' && wsNames.length > 1) {
      e.preventDefault();
      wsSelect._prevValue = wsSelect.value;
      wsSelect.focus();
      return;
    }
    if ('hjkl'.includes(e.key)) {
      e.preventDefault();
      navigateVim(e.key);
    }
    if (e.key === 'Enter' && selectedNode) {
      e.preventDefault();
      enterFocus(selectedNode);
    }
    if (e.key === 'o' && selectedNode) {
      e.preventDefault();
      const nd = nodesDS.get(selectedNode);
      if (nd) {
        const filePath = resolveFilePath(nd);
        if (filePath) openInNvim(filePath);
      }
    }
  };
  document.addEventListener('keydown', window._graphKeyHandler);
}

// ── Reset view ────────────────────────────────────────────────────────────
function resetView() {
  if (network) network.fit({ animation: { duration: 600, easingFunction: 'easeInOutQuad' } });
}

// ── Resize ────────────────────────────────────────────────────────────────
window.addEventListener('resize', () => {
  if (network) network.redraw();
});

// ── Server lifecycle: shutdown on tab close, heartbeat as fallback ────────
if (IS_SERVER_MODE) {
  window.addEventListener('beforeunload', () => {
    navigator.sendBeacon('/api/shutdown');
  });
  setInterval(() => fetch('/api/heartbeat').catch(() => {}), 30000);
}

// ── Initial render ────────────────────────────────────────────────────────
renderGraph(ACTIVE_WORKSPACE);
</script>
</body>
</html>
"""


# ── Generate HTML ─────────────────────────────────────────────────────────────

def generate_html(workspaces_data: dict, active: str) -> str:
    html = HTML_TEMPLATE
    html = html.replace("__WORKSPACES_DATA__", json.dumps(workspaces_data, ensure_ascii=False))
    html = html.replace("__ACTIVE_WORKSPACE__", active)
    return html


# ── Browser open / refresh ────────────────────────────────────────────────────

def open_or_refresh(url: str, chromium_apps=None):
    """Refresh existing browser tab if open, otherwise open a new one."""
    if chromium_apps is None:
        chromium_apps = DEFAULT_CHROMIUM_APPS

    if sys.platform == "darwin":
        # Try each configured Chromium-based browser, then Safari, via AppleScript.
        candidates = [(app, _chromium_applescript(app, url)) for app in chromium_apps]
        candidates.append(("Safari", _safari_applescript(url)))
        for browser, script in candidates:
            try:
                result = subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip() == "found":
                    print(f"Refreshed in {browser}")
                    return
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue

    # Fallback: open new tab
    webbrowser.open(url)
    print("Opening in browser...")


def _chromium_applescript(app: str, url: str) -> str:
    return f'''
tell application "System Events"
    if not (exists process "{app}") then return "missing"
end tell
tell application "{app}"
    repeat with w in windows
        set ti to 0
        repeat with t in tabs of w
            set ti to ti + 1
            if URL of t starts with "{url}" then
                set active tab index of w to ti
                set index of w to 1
                tell t to reload
                return "found"
            end if
        end repeat
    end repeat
end tell
return "notfound"
'''


def _safari_applescript(url: str) -> str:
    return f'''
tell application "System Events"
    if not (exists process "Safari") then return "missing"
end tell
tell application "Safari"
    repeat with w in windows
        repeat with t in tabs of w
            if URL of t starts with "{url}" then
                set current tab of w to t
                set index of w to 1
                tell t to do JavaScript "location.reload()"
                return "found"
            end if
        end repeat
    end repeat
end tell
return "notfound"
'''


# ── HTTP server mode (for open-in-nvim) ──────────────────────────────────────

def kill_previous_server():
    """Kill a previously running llm-kiwi server."""
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            os.kill(old_pid, signal.SIGTERM)
            time.sleep(0.3)
        except (ProcessLookupError, ValueError, PermissionError, OSError):
            pass
        PID_FILE.unlink(missing_ok=True)


IDLE_TIMEOUT = 90  # seconds — auto-stop if no heartbeat


def start_server(html_content: str, nvim_server: str, no_open: bool, chromium_apps=None):
    """Start HTTP server that serves the graph and handles open-in-nvim requests."""
    kill_previous_server()
    PID_FILE.write_text(str(os.getpid()))

    import time
    last_activity = time.time()
    running = True

    class Handler(http.server.BaseHTTPRequestHandler):
        def _json(self, body: bytes = b'{"ok":true}'):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            nonlocal last_activity
            last_activity = time.time()
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path in ('/', '/index.html'):
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Cache-Control', 'no-store, must-revalidate')
                self.end_headers()
                self.wfile.write(html_content.encode('utf-8'))
            elif parsed.path == '/api/open':
                params = urllib.parse.parse_qs(parsed.query)
                file_path = params.get('path', [None])[0]
                if file_path and nvim_server:
                    try:
                        subprocess.run(['nvim', '--server', nvim_server, '--remote', file_path], capture_output=True, timeout=5)
                    except Exception:
                        pass
                self._json()
            elif parsed.path == '/api/cwd':
                cwd = ''
                if nvim_server:
                    try:
                        result = subprocess.run(['nvim', '--server', nvim_server, '--remote-expr', 'getcwd()'], capture_output=True, text=True, timeout=5)
                        cwd = result.stdout.strip()
                    except Exception:
                        pass
                self._json(json.dumps({"cwd": cwd}).encode())
            elif parsed.path == '/api/open-in-tmux':
                params = urllib.parse.parse_qs(parsed.query)
                file_path = params.get('path', [None])[0]
                vault_path = params.get('vault', [None])[0]
                opened = False
                if file_path and vault_path:
                    try:
                        tmux_check = subprocess.run(['tmux', 'list-sessions'], capture_output=True, timeout=3)
                        if tmux_check.returncode == 0:
                            win_check = subprocess.run(['tmux', 'list-windows', '-F', '#{window_name}'], capture_output=True, text=True, timeout=3)
                            if 'vault' in (win_check.stdout or '').split('\n'):
                                subprocess.run(['tmux', 'select-window', '-t', 'vault'], capture_output=True, timeout=3)
                                subprocess.run(['tmux', 'send-keys', '-t', 'vault', f':e {file_path}', 'Enter'], capture_output=True, timeout=3)
                            else:
                                subprocess.run(['tmux', 'new-window', '-n', 'vault', '-c', vault_path, 'nvim', file_path], capture_output=True, timeout=5)
                            opened = True
                    except Exception:
                        pass
                self._json(json.dumps({"ok": opened, "tmux": opened}).encode())
            elif parsed.path == '/api/heartbeat':
                self._json()
            elif parsed.path == '/api/shutdown':
                nonlocal running
                running = False
                self._json()
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            nonlocal running, last_activity
            last_activity = time.time()
            if urllib.parse.urlparse(self.path).path == '/api/shutdown':
                running = False
            self._json()

        def log_message(self, format, *args):
            pass

    http.server.HTTPServer.allow_reuse_address = True
    server = http.server.HTTPServer(('127.0.0.1', SERVER_PORT), Handler)

    url = f'http://127.0.0.1:{SERVER_PORT}'
    print(f'Serving graph at {url}')

    if not no_open:
        open_or_refresh(url, chromium_apps)

    def handle_sigterm(signum, frame):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, handle_sigterm)

    server.timeout = 0.5
    try:
        while running:
            server.handle_request()
            if time.time() - last_activity > IDLE_TIMEOUT:
                print('Idle timeout, shutting down')
                break
    except KeyboardInterrupt:
        pass
    finally:
        try:
            subprocess.run(['tmux', 'kill-window', '-t', 'vault'], capture_output=True, timeout=3)
        except Exception:
            pass
        PID_FILE.unlink(missing_ok=True)
        print('Server stopped')
    return 0


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    if not args.vaults:
        print("Error: no vaults specified. Use --vault NAME=PATH (repeatable).")
        return 1

    # Collect vaults (first wins on duplicate names)
    vaults_to_scan: dict[str, Path] = {}
    for name, path in args.vaults:
        if name in vaults_to_scan:
            print(f"Warning: duplicate vault name '{name}', keeping first")
            continue
        vaults_to_scan[name] = path

    active_name = args.active if args.active and args.active in vaults_to_scan else next(iter(vaults_to_scan))

    # Scan all vaults
    workspaces_data = {}
    for name, vault_path in vaults_to_scan.items():
        if not vault_path.exists():
            print(f"Warning: skipping {name} — path does not exist: {vault_path}")
            continue
        print(f"Scanning {name}: {vault_path}")
        nodes, links = scan_vault(vault_path)
        real_count = sum(1 for n in nodes if n['group'] != 'unresolved')
        print(f"  {real_count} notes, {len(links)} links")
        workspaces_data[name] = {"nodes": nodes, "links": links, "vault_path": str(vault_path)}

    if not workspaces_data:
        print("Error: no valid vaults to scan.")
        return 1

    if active_name not in workspaces_data:
        active_name = next(iter(workspaces_data))

    html = generate_html(workspaces_data, active_name)

    # Server mode: serve via HTTP with open-in-nvim API
    if args.nvim_server:
        return start_server(html, args.nvim_server, args.no_open, args.chromium_apps)

    # File mode: write HTML and open in browser
    if args.output:
        out_path = Path(args.output).expanduser()
    else:
        all_paths = list(vaults_to_scan.values())
        root = Path(os.path.commonpath([str(p) for p in all_paths]))
        out_path = root / "graph.html"

    out_path.write_text(html, encoding="utf-8")

    print(f"Graph saved: {out_path}")

    if not args.no_open:
        open_or_refresh(f"file://{out_path}", args.chromium_apps)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
