const API = window.location.origin;
let activeSector = '';
let _agentMode = false;
let _loadMode = false;
let _loadBuffer = [];
let _loadingCount = 0;
let _conversationHistory = [];

/* ── Init ── */
document.addEventListener('DOMContentLoaded', async () => {
  const input = document.getElementById('terminal-input');
  input.addEventListener('keydown', e => { if (e.key === 'Enter') handleCommand(); });
  input.focus();
  document.getElementById('terminal-container').addEventListener('click', () => input.focus());

  updatePrompt();

  printBanner();
});

/* ── View Switching ── */
function switchView(view) {
  document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.view === view));
  document.querySelectorAll('.admin-view').forEach(v => v.classList.toggle('active', v.id === `view-${view}`));
  if (view === 'terminal') {
    const input = document.getElementById('terminal-input');
    if (input) input.focus();
  }
  if (view === 'dashboard') loadDashboard();
  if (view === 'knowledge') loadKnowledge();
}

/* ── Terminal Output ── */
function termWrite(text, cls = 'stdout') {
  const out = document.getElementById('terminal-output');
  const line = document.createElement('div');
  line.className = `term-line ${cls}`;
  line.innerHTML = text;
  out.appendChild(line);
  out.scrollTop = out.scrollHeight;
}

function termSep() {
  const out = document.getElementById('terminal-output');
  out.appendChild(document.createElement('hr')).className = 'term-sep';
}

function termSpan(text, cls) {
  return `<span class="${cls}">${escapeHtml(text)}</span>`;
}

function escapeHtml(t) {
  if (t == null) return '';
  const d = document.createElement('div');
  d.textContent = String(t);
  return d.innerHTML;
}

function updatePrompt() {
  const el = document.getElementById('terminal-prompt');
  if (el) el.textContent = activeSector ? `grac-admin[${activeSector}]>` : 'grac-admin>';
}

/* ── Banner ── */
function printBanner() {
  termWrite(`
  <span class="term-banner">╔══════════════════════════════════════════════════════╗
  ║   GRaC Operations Console — v1.0                      ║
  ║   Governance, Risk & Compliance Agent                 ║
  ║   Ghana AI Innovation Challenge 2026                  ║
  ╚══════════════════════════════════════════════════════╝</span>`, 'stdout');
  termWrite(`No sector selected. Use <span class="accent">use &lt;sector_id&gt;</span> to begin.`, 'info');
  termSep();
}

/* ── Loading ── */
let _loadingTimer = null;

function showLoading(msg = 'Processing...') {
  _loadingCount++;
  clearTimeout(_loadingTimer);
  let overlay = document.getElementById('terminal-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'terminal-overlay';
    overlay.innerHTML = '<div class="overlay-box"><div class="overlay-spinner"></div><div class="overlay-msg"></div></div>';
    document.body.appendChild(overlay);
  }
  overlay.querySelector('.overlay-msg').textContent = msg;
  overlay.classList.add('show');
  _loadingTimer = setTimeout(() => {
    _loadingCount = 0;
    const el = document.getElementById('terminal-overlay');
    if (el) { el.classList.remove('show'); el.remove(); }
  }, 120000);
}

function hideLoading() {
  _loadingCount--;
  clearTimeout(_loadingTimer);
  if (_loadingCount <= 0) { _loadingCount = 0;
    const overlay = document.getElementById('terminal-overlay');
    if (overlay) {
      overlay.classList.remove('show');
      overlay.remove();
    }
  }
}

/* ═══════════════════════════════════════════
   COMMAND ENGINE
   ═══════════════════════════════════════════ */

function setInput(placeholder) {
  const input = document.getElementById('terminal-input');
  input.placeholder = placeholder || 'type help for commands';
  input.focus();
}

async function handleCommand() {
  const input = document.getElementById('terminal-input');
  const raw = input.value.trim();
  input.value = '';
  if (!raw && !_loadMode) return;

  // ── Load mode (multi-line paste) ──
  if (_loadMode) {
    if (raw === '..' || raw === '---END---') {
      _loadMode = false;
      setInput();
      const fullText = _loadBuffer.join('\n');
      _loadBuffer = [];
      if (!fullText.trim()) {
        termWrite(`<span class="amber">Cancelled (empty input).</span>`, 'warning');
        return;
      }
      termWrite(`${termSpan('grac-admin[load]>', 'purple')} (${fullText.length} chars received)`, 'stdout');
      await cmdAnalyzeRaw(fullText);
      return;
    }
    _loadBuffer.push(raw);
    termWrite(`${termSpan('grac-admin[load]>', 'purple')} ${escapeHtml(raw)}`, 'stdout');
    return;
  }

  // ── Agent mode (interactive conversation) ──
  if (_agentMode) {
    if (raw === '..' || raw === 'exit agent') {
      _agentMode = false;
      setInput();
      termWrite(`<span class="amber">Exited agent mode.</span>`, 'warning');
      return;
    }
    termWrite(`${termSpan('grac-agent>', 'cyan')} ${escapeHtml(raw)}`, 'stdout');
    await cmdAskRaw(raw);
    return;
  }

  // ── Normal command mode ──
  const promptLabel = activeSector ? `grac-admin[${activeSector}]>` : 'grac-admin>';
  termWrite(`${termSpan(promptLabel, 'green')} ${escapeHtml(raw)}`, 'stdout');

  const parts = raw.split(/\s+/);
  const cmd = parts[0].toLowerCase();
  const args = parts.slice(1);

  try {
    switch (cmd) {
      case 'help': cmdHelp(); break;
      case 'status': await cmdStatus(); break;
      case 'sectors': await cmdSectors(args); break;
      case 'use': await cmdUse(args); break;
      case 'ingest': await cmdIngest(args); break;
      case 'train': await cmdIngest(args); break;
      case 'upload': cmdUpload(args); break;
      case 'ask': await cmdAsk(args); break;
      case 'analyze': await cmdAnalyze(args); break;
      case 'score': await cmdScore(args); break;
      case 'laws': await cmdLaws(args); break;
      case 'delete': await cmdDelete(args); break;
      case 'agent': await enterAgentMode(); break;
      case 'load': enterLoadMode(); break;
      case 'paste': enterLoadMode(); break;
      case 'draft': await cmdDraft(args); break;
      case 'knowledge': await cmdKnowledge(); break;
      case 'clear': case 'cls': cmdClear(); break;
      default:
        termWrite(`Unknown: <span class="amber">${escapeHtml(cmd)}</span>. Type <span class="accent">help</span>.`, 'stderr');
    }
  } catch (e) {
    termWrite(`Error: ${escapeHtml(e.message || 'Request failed')}`, 'stderr');
    hideLoading();
  }
}

/* ═══════════════════════════════════════════
   COMMAND: help
   ═══════════════════════════════════════════ */

function cmdHelp() {
  const sec = activeSector ? `<span class="accent">${escapeHtml(activeSector)}</span>` : '<span class="amber">none — use &lt;sector&gt; first</span>';
  termWrite(`
<span class="bold">╔══════════════════════════════════════════════════╗
║   GRaC Operations Console — Command Reference      ║
╚══════════════════════════════════════════════════╝</span>

<span class="accent bold">═══ SECTOR MANAGEMENT ═══</span>
  <span class="accent">use &lt;sector_id&gt;</span>       Switch active sector (current: ${sec})
  <span class="accent">sectors</span>                List all sectors and their status
  <span class="accent">sector enable &lt;id&gt;</span>   Enable a sector
  <span class="accent">sector disable &lt;id&gt;</span>  Disable a sector

<span class="accent bold">═══ LAW FILES ═══</span>
  <span class="accent">laws &lt;sector&gt;</span>           List PDF files in a sector
  <span class="accent">upload &lt;sector&gt;</span>        Upload PDF(s) to a sector (opens file picker)
  <span class="accent">delete &lt;sector&gt; &lt;file&gt;</span>  Delete a PDF from a sector
  <span class="accent">delete &lt;sector&gt; all</span>     Delete ALL PDFs from a sector
  <span class="accent">ingest &lt;sector&gt;</span>        Parse &amp; embed laws for a sector
  <span class="accent">ingest all</span>              Ingest all enabled sectors

<span class="accent bold">═══ COMPLIANCE QUERIES ═══</span>
  <span class="accent">ask &lt;question&gt;</span>         Ask a compliance question (uses active sector)
  <span class="accent">analyze &lt;text&gt;</span>         Analyze policy text for regulatory gaps
  <span class="accent">score &lt;text&gt;</span>           Calculate compliance score against laws

<span class="accent bold">═══ DOCUMENT GENERATION ═══</span>
  <span class="accent">draft &lt;topic&gt;</span>         Generate a compliance policy draft PDF
                          Example: <span class="accent">draft</span> data breach notification policy
                          Downloads a PDF written with law references

<span class="accent bold">═══ INTERACTIVE MODES ═══</span>
  <span class="accent">agent</span>                  Enter interactive agent conversation mode
                          Type questions freely; type <span class="amber">..</span> or <span class="amber">exit agent</span> to quit
  <span class="accent">load</span>                    Multi-line paste mode for large text
                          Type/paste your text, then <span class="amber">..</span> on its own line to finish
                          The text will be analyzed automatically

<span class="accent bold">═══ SYSTEM ═══</span>
  <span class="accent">status</span>                  System health &amp; statistics
  <span class="accent">knowledge</span>               Show loaded laws per sector
  <span class="accent">clear</span>                   Clear terminal

<span class="bold">═══ QUICK START WORKFLOWS ═══</span>

  1. <span class="green">Add a new law:</span>
     <span class="dim">upload healthcare        → pick PDF file(s)</span>
     <span class="dim">ingest healthcare        → parse &amp; vectorize</span>

  2. <span class="green">Test a sector:</span>
     <span class="dim">use cybersecurity        → set active sector</span>
     <span class="dim">ask what are the penalties for non-compliance?</span>

  3. <span class="green">Analyze a policy document:</span>
     <span class="dim">load                    → paste your policy text</span>
     <span class="dim">..                       → finish &amp; auto-analyze</span>

  4. <span class="green">Interactive agent session:</span>
     <span class="dim">agent                   → enter chat mode</span>
     <span class="dim">what laws apply to mobile money operators?</span>
     <span class="dim">analyze: Our policy requires X...  → ask in context</span>
     <span class="dim">..                       → exit agent mode</span>
`, 'stdout');
}

/* ═══════════════════════════════════════════
   COMMAND: use <sector>
   ═══════════════════════════════════════════ */

async function cmdUse(args) {
  const id = args[0];
  if (!id) {
    termWrite(`Usage: <span class="accent">use</span> &lt;sector_id&gt;`, 'stderr');
    termWrite(`Current: <span class="accent">${activeSector || 'none'}</span>`, 'info');
    return;
  }
  const r = await fetch(`${API}/api/admin/sectors`);
  const d = await r.json();
  const match = (d.sectors || []).find(s => s.id === id);
  if (!match) {
    termWrite(`Unknown sector: <span class="amber">${escapeHtml(id)}</span>`, 'stderr');
    return;
  }
  if (!match.enabled) {
    termWrite(`Sector <span class="amber">${escapeHtml(id)}</span> is disabled. Enable it first: <span class="accent">sector enable ${escapeHtml(id)}</span>`, 'warning');
  }
  activeSector = match.id;
  updatePrompt();
  const ready = match.has_collection ? `<span class="green">ready</span>` : `<span class="amber">not ingested</span>`;
  termWrite(`Active sector: <span class="accent">${escapeHtml(match.name)}</span> (${match.pdf_count} PDFs, ${ready})`, 'success');
}

/* ═══════════════════════════════════════════
   COMMAND: status
   ═══════════════════════════════════════════ */

async function cmdStatus() {
  termWrite(`Fetching system status...`, 'info');
  const r = await fetch(`${API}/api/admin/sectors`);
  const data = await r.json();
  const sectors = data.sectors || [];

  const total = sectors.length;
  const enabled = sectors.filter(s => s.enabled).length;
  const totalPdfs = sectors.reduce((s, sec) => s + sec.pdf_count, 0);
  const parsed = sectors.reduce((s, sec) => s + sec.parsed_count, 0);
  const ingested = sectors.filter(s => s.has_collection).length;

  const kr = await fetch(`${API}/api/system/knowledge`);
  const kinfo = await kr.json();

  termWrite('');
  termWrite(`<span class="bold">System Status</span>`, 'highlight');
  termSep();
  termWrite(`
  <span class="dim">System:</span>    ${escapeHtml(kinfo.system_name)} v${escapeHtml(kinfo.version)}
  <span class="dim">Jurisdiction:</span> ${escapeHtml(kinfo.jurisdiction)}
  <span class="dim">Sectors:</span>   ${total} total, ${enabled} active, ${ingested} vectorized
  <span class="dim">PDFs:</span>      ${totalPdfs} raw, ${parsed} parsed
  <span class="dim">Status:</span>    ${kinfo.status}`, 'stdout');
  termSep();

  for (const s of sectors) {
    const icon = s.enabled ? (s.has_collection ? termSpan('READY', 'green') : termSpan('EMPTY', 'amber')) : termSpan('OFF', 'red');
    const marker = s.id === activeSector ? termSpan(' ← ACTIVE', 'cyan') : '';
    const laws = s.laws.length ? s.laws.join(', ') : '<span class="dim">none configured</span>';
    termWrite(`  [${icon}] <span class="bold">${escapeHtml(s.name)}</span> <span class="dim">(${escapeHtml(s.id)})</span>${marker}`, 'stdout');
    termWrite(`         PDFs: ${s.pdf_count}  Parsed: ${s.parsed_count}  Laws: ${laws}`, 'stdout');
  }
  termWrite('');
}

/* ═══════════════════════════════════════════
   COMMAND: sectors
   ═══════════════════════════════════════════ */

async function cmdSectors(args) {
  const r = await fetch(`${API}/api/admin/sectors`);
  const data = await r.json();
  const sectors = data.sectors || [];

  if (args.length > 0 && args[0] === 'test') {
    const testReady = sectors.filter(s => s.has_collection);
    if (testReady.length === 0) {
      termWrite(`No sectors with ingested laws. Ingest one first.`, 'warning');
      return;
    }
    termWrite(`<span class="bold">Sectors ready for testing:</span>`, 'highlight');
    termSep();
    for (const s of testReady) {
      const marker = s.id === activeSector ? termSpan(' ← ACTIVE (use for testing)', 'cyan') : '';
      termWrite(`  [${termSpan('READY', 'green')}] <span class="bold">${escapeHtml(s.name)}</span> <span class="dim">(${escapeHtml(s.id)})</span>${marker}`, 'stdout');
      termWrite(`         Laws: ${s.laws.join(', ') || '<span class="dim">none</span>'}`, 'stdout');
    }
    termWrite(`
Use <span class="accent">use &lt;sector_id&gt;</span> to switch context, then <span class="accent">ask</span>, <span class="accent">analyze</span>, or <span class="accent">agent</span>.`, 'info');
    return;
  }

  termWrite(`<span class="bold">Sectors</span>`, 'highlight');
  termSep();
  for (const s of sectors) {
    const icon = s.enabled ? (s.has_collection ? termSpan('READY', 'green') : termSpan('EMPTY', 'amber')) : termSpan('OFF', 'red');
    const marker = s.id === activeSector ? termSpan(' ← ACTIVE', 'cyan') : '';
    const laws = s.laws.length ? s.laws.join(', ') : '<span class="dim">none</span>';
    termWrite(`  [${icon}] <span class="bold">${escapeHtml(s.name)}</span> <span class="dim">(${escapeHtml(s.id)})</span>${marker}`, 'stdout');
    termWrite(`         PDFs: ${s.pdf_count}  Parsed: ${s.parsed_count}  Laws: ${laws}`, 'stdout');
  }
  termWrite(`
Tip: <span class="accent">sectors test</span> shows only ready sectors.
Tip: <span class="accent">use &lt;id&gt;</span> to switch active sector.`, 'info');
}

/* ═══════════════════════════════════════════
   COMMAND: ingest / train
   ═══════════════════════════════════════════ */

async function cmdIngest(args) {
  const target = args[0] ? args[0].toLowerCase() : (activeSector || 'all');
  if (target === 'all') {
    const r = await fetch(`${API}/api/admin/sectors`);
    const data = await r.json();
    const toIngest = data.sectors.filter(s => s.enabled && s.pdf_count > 0);
    if (toIngest.length === 0) {
      termWrite(`No sectors with PDFs to ingest. Upload some first: <span class="accent">upload &lt;sector&gt;</span>`, 'warning');
      return;
    }
    termWrite(`Ingesting <span class="bold">${toIngest.length}</span> sector(s)...`, 'info');
    for (const s of toIngest) {
      await ingestOne(s.id);
    }
    termWrite(`<span class="green">All sectors ingested.</span>`, 'success');
    return;
  }
  await ingestOne(target);
}

async function ingestOne(sectorId) {
  termWrite(`  <span class="term-progress"></span> Ingesting <span class="accent">${escapeHtml(sectorId)}</span>...`, 'stdout');
  showLoading(`Ingesting ${sectorId}...`);
  try {
    const r = await fetch(`${API}/api/admin/sectors/${sectorId}/ingest`, { method: 'POST' });
    const d = await r.json();
    if (d.status === 'ok') {
      termWrite(`  <span class="green">✓</span> ${d.pdfs_processed} PDF(s) ingested in ${d.elapsed_seconds}s`, 'success');
    } else {
      termWrite(`  <span class="red">✗</span> ${escapeHtml(d.detail || 'unknown error')}`, 'stderr');
    }
  } catch (e) {
    termWrite(`  <span class="red">✗</span> ${escapeHtml(e.message)}`, 'stderr');
  } finally {
    hideLoading();
  }
}

/* ═══════════════════════════════════════════
   COMMAND: upload
   ═══════════════════════════════════════════ */

let _pendingUploadSector = null;

function cmdUpload(args) {
  const sector = args[0] || activeSector;
  if (!sector) {
    termWrite(`Usage: <span class="accent">upload</span> &lt;sector_id&gt;`, 'stderr');
    return;
  }
  _pendingUploadSector = sector;
  const btn = document.getElementById('term-upload-btn');
  btn.textContent = `+ Upload to ${sector}`;
  btn.classList.add('active');
  btn.disabled = false;
  // Clickable prompt in the terminal output
  termWrite(`Click here to select PDF(s) for <span class="accent">${escapeHtml(sector)}</span>: <span class="cyan" id="term-inline-upload-btn" style="cursor:pointer;text-decoration:underline">[Select Files]</span>`, 'info');
}

function onUploadBtnClick(event) {
  const sector = _pendingUploadSector;
  if (!sector) {
    termWrite(`Set a sector first: <span class="accent">upload &lt;sector_id&gt;</span>`, 'stderr');
    return;
  }
  openFilePicker();
}

// Click handler for the inline [Select Files] text in terminal output
document.addEventListener('DOMContentLoaded', () => {
  document.addEventListener('click', e => {
    if (e.target && e.target.id === 'term-inline-upload-btn') {
      openFilePicker();
    }
  });
});

function openFilePicker() {
  // Create a fresh input each time to avoid stale state
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.pdf';
  input.multiple = true;
  input.style.display = 'none';
  document.body.appendChild(input);

  input.addEventListener('change', async function handler(e) {
    const files = e.target.files;
    const sector = _pendingUploadSector;
    if (!files || !files.length || !sector) {
      _pendingUploadSector = null;
      resetUploadBtn();
      document.body.removeChild(input);
      if (files && !files.length && sector) {
        termWrite(`<span class="amber">No files selected.</span>`, 'warning');
      }
      return;
    }
    _pendingUploadSector = null;
    resetUploadBtn();

    let uploaded = 0;
    for (const file of files) {
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        termWrite(`  <span class="amber">Skipping</span> ${escapeHtml(file.name)} (not a PDF)`, 'warning');
        continue;
      }
      termWrite(`  Uploading <span class="accent">${escapeHtml(file.name)}</span> to <span class="accent">${escapeHtml(sector)}</span>...`, 'info');
      const form = new FormData();
      form.append('file', file);
      try {
        const r = await fetch(`${API}/api/admin/sectors/${sector}/upload`, { method: 'POST', body: form });
        const d = await r.json();
        if (d.status === 'ok') {
          termWrite(`  <span class="green">✓</span> ${escapeHtml(file.name)} (${(d.size/1024).toFixed(0)} KB)`, 'success');
          uploaded++;
        } else {
          termWrite(`  <span class="red">✗</span> ${escapeHtml(d.detail || 'upload failed')}`, 'stderr');
        }
      } catch (e) {
        termWrite(`  <span class="red">✗</span> ${escapeHtml(e.message)}`, 'stderr');
      }
    }
    document.body.removeChild(input);
    if (uploaded > 0) {
      termWrite(`  <span class="green">✓</span> ${uploaded} file(s) uploaded to <span class="accent">${escapeHtml(sector)}</span>`, 'success');
      termWrite(`  Next: <span class="accent">ingest ${escapeHtml(sector)}</span> to parse &amp; embed`, 'info');
    }
  });

  input.click();
}

function resetUploadBtn() {
  const btn = document.getElementById('term-upload-btn');
  btn.textContent = '+ Upload';
  btn.classList.remove('active');
}

/* ═══════════════════════════════════════════
   COMMAND: laws <sector>
   ═══════════════════════════════════════════ */

async function cmdLaws(args) {
  const sector = args[0] || activeSector;
  if (!sector) {
    termWrite(`Usage: <span class="accent">laws</span> &lt;sector_id&gt;`, 'stderr');
    return;
  }
  const r = await fetch(`${API}/api/admin/sectors`);
  const data = await r.json();
  const sec = (data.sectors || []).find(s => s.id === sector);
  if (!sec) {
    termWrite(`Unknown sector: <span class="amber">${escapeHtml(sector)}</span>`, 'stderr');
    return;
  }

  termWrite(`<span class="bold">${escapeHtml(sec.name)}</span> <span class="dim">(${escapeHtml(sec.id)})</span>`, 'highlight');
  termSep();

  if (sec.pdfs.length === 0) {
    termWrite(`No PDFs uploaded yet.`, 'warning');
    termWrite(`Upload: <span class="accent">upload ${escapeHtml(sector)}</span>`, 'info');
  } else {
    termWrite(`<span class="dim">${sec.pdfs.length} file(s):</span>`, 'info');
    for (const p of sec.pdfs) {
      termWrite(`  <span class="cyan">${escapeHtml(p.name)}</span>  <span class="dim">${(p.size / 1024).toFixed(0)} KB</span>`, 'stdout');
    }
    termWrite(``);
    termWrite(`Ingest: <span class="accent">ingest ${escapeHtml(sector)}</span>    Delete: <span class="accent">delete ${escapeHtml(sector)} &lt;filename&gt;</span>`, 'info');
  }
}

/* ═══════════════════════════════════════════
   COMMAND: delete <sector> <filename>
   ═══════════════════════════════════════════ */

async function cmdDelete(args) {
  const sector = args[0] || activeSector;
  const filename = args.slice(1).join(' ');

  if (!sector) {
    termWrite(`Usage: <span class="accent">delete</span> &lt;sector_id&gt; &lt;filename&gt;`, 'stderr');
    termWrite(`       <span class="accent">delete</span> &lt;sector_id&gt; <span class="amber">all</span>  — delete ALL PDFs in sector`, 'info');
    return;
  }

  // Delete all
  if (args[0] && args[1] && args[1].toLowerCase() === 'all') {
    if (!confirm(`Delete ALL PDFs in '${args[0]}'?`)) {
      termWrite(`Cancelled.`, 'warning');
      return;
    }
    termWrite(`Deleting all PDFs in <span class="accent">${escapeHtml(args[0])}</span>...`, 'info');
    try {
      const r = await fetch(`${API}/api/admin/sectors/${args[0]}/pdfs`, { method: 'DELETE' });
      const d = await r.json();
      if (d.status === 'ok') {
        termWrite(`<span class="green">✓</span> Deleted ${d.count} PDF(s) from ${escapeHtml(args[0])}`, 'success');
      } else {
        termWrite(`<span class="red">✗</span> ${escapeHtml(d.detail || 'delete failed')}`, 'stderr');
      }
    } catch (e) {
      termWrite(`<span class="red">✗</span> ${escapeHtml(e.message)}`, 'stderr');
    }
    return;
  }

  // Delete single file
  if (!filename) {
    termWrite(`Usage: <span class="accent">delete</span> &lt;sector_id&gt; &lt;filename&gt;`, 'stderr');
    return;
  }

  if (!confirm(`Delete '${filename}' from '${sector}'?`)) {
    termWrite(`Cancelled.`, 'warning');
    return;
  }

  termWrite(`Deleting <span class="accent">${escapeHtml(filename)}</span> from <span class="accent">${escapeHtml(sector)}</span>...`, 'info');
  try {
    const r = await fetch(`${API}/api/admin/sectors/${sector}/pdfs/${encodeURIComponent(filename)}`, { method: 'DELETE' });
    const d = await r.json();
    if (d.status === 'ok') {
      termWrite(`<span class="green">✓</span> Deleted ${escapeHtml(filename)}`, 'success');
    } else {
      termWrite(`<span class="red">✗</span> ${escapeHtml(d.detail || 'delete failed')}`, 'stderr');
    }
  } catch (e) {
    termWrite(`<span class="red">✗</span> ${escapeHtml(e.message)}`, 'stderr');
  }
}

/* ═══════════════════════════════════════════
   COMMAND: ask
   ═══════════════════════════════════════════ */

async function cmdAsk(args) {
  const question = args.join(' ');
  if (!question) {
    termWrite(`Usage: <span class="accent">ask</span> &lt;question&gt; (uses active sector: ${activeSector || 'none'})`, 'stderr');
    return;
  }
  await cmdAskRaw(question);
}

async function cmdAskRaw(question) {
  const sectorLabel = activeSector || 'all sectors';
  termWrite(`  <span class="term-progress"></span> Processing...`, 'info');
  showLoading('Processing...');
  try {
    const form = new FormData();
    form.append('question', question);
    if (activeSector) form.append('sector', activeSector);
    form.append('history', JSON.stringify(_conversationHistory));
    const r = await fetch(`${API}/api/admin/test`, { method: 'POST', body: form });
    const d = await r.json();
    const answer = d?.result?.answer || d?.answer || JSON.stringify(d);
    const sources = d?.result?.sources || d?.sources || [];
    const qtype = d?.result?.query_type || 'compliance';
    _conversationHistory.push({ role: 'user', content: question });
    _conversationHistory.push({ role: 'assistant', content: answer });
    termWrite('', 'stdout');
    termWrite(`<span class="accent">Answer:</span>`, 'highlight');
    termWrite(escapeHtml(answer), 'stdout');
    if (sources.length > 0) {
      const srcLabel = qtype === 'research' ? 'Web Sources' : 'Sources';
      termWrite(`<span class="dim">${srcLabel} (${sources.length}):</span>`, 'info');
      for (const s of sources) {
        if (s.source === 'web') {
          termWrite(`  <span class="src-law">${escapeHtml(s.title || 'Unknown')}</span>`, 'stdout');
          if (s.url) termWrite(`  <span class="dim">${escapeHtml(s.url)}</span>`, 'stdout');
        } else {
          const law = s.law_name || 'Unknown';
          const sec = s.section_number ? ` §${escapeHtml(s.section_number)}` : '';
          const secName = s.sector ? ` [${escapeHtml(s.sector)}]` : '';
          const text = (s.text || '').slice(0, 200);
          termWrite(`  <span class="src-law">${escapeHtml(law)}${sec}${secName}</span>`, 'stdout');
          termWrite(`  <span class="dim">${escapeHtml(text)}</span>`, 'stdout');
        }
      }
    }
  } catch (e) {
    termWrite(`<span class="red">✗</span> ${escapeHtml(e.message)}`, 'stderr');
  } finally {
    hideLoading();
  }
}

/* ═══════════════════════════════════════════
   COMMAND: analyze
   ═══════════════════════════════════════════ */

async function cmdAnalyze(args) {
  const text = args.join(' ');
  if (!text) {
    termWrite(`Usage: <span class="accent">analyze</span> &lt;policy_text&gt;`, 'stderr');
    termWrite(`For large text, use <span class="accent">load</span> (multi-line paste mode).`, 'info');
    return;
  }
  if (text.length < 20) {
    termWrite(`Text too short (min 20 chars).`, 'stderr');
    return;
  }
  await cmdAnalyzeRaw(text);
}

async function cmdAnalyzeRaw(text) {
  if (!activeSector) {
    termWrite(`No active sector. Set one: <span class="accent">use &lt;sector_id&gt;</span>`, 'stderr');
    return;
  }
  termWrite(`  <span class="term-progress"></span> Analyzing against ${escapeHtml(activeSector)} laws...`, 'info');
  showLoading('Analyzing...');
  try {
    const form = new FormData();
    form.append('question', text);
    form.append('sector', activeSector);
    const r = await fetch(`${API}/api/admin/test`, { method: 'POST', body: form });
    const d = await r.json();
    const analysis = d?.result?.analysis || d?.analysis || d;
    const gaps = analysis.gaps || [];
    const summary = analysis.summary || '';
    termWrite('', 'stdout');
    if (gaps.length > 0) {
      termWrite(`<span class="accent">Gap Analysis (${gaps.length} findings):</span>`, 'highlight');
      for (const g of gaps.slice(0, 10)) {
        const sev = (g.severity || 'medium').toUpperCase();
        const sevCls = sev === 'HIGH' ? 'red' : sev === 'LOW' ? 'green' : 'amber';
        termWrite(`  <span class="${sevCls}">[${sev}]</span> ${escapeHtml(g.requirement || '')}`, 'stdout');
        termWrite(`  <span class="dim">  Law: ${escapeHtml(g.law_reference || '')}</span>`, 'stdout');
        termWrite(`  <span class="dim">  Status: ${escapeHtml(g.policy_status || '')}</span>`, 'stdout');
      }
    } else {
      termWrite(`No gaps identified.`, 'success');
    }
    if (summary) termWrite(`<span class="bold">Summary:</span> ${escapeHtml(summary)}`, 'stdout');
  } catch (e) {
    termWrite(`<span class="red">✗</span> ${escapeHtml(e.message)}`, 'stderr');
  } finally {
    hideLoading();
  }
}

/* ═══════════════════════════════════════════
   COMMAND: score
   ═══════════════════════════════════════════ */

async function cmdScore(args) {
  const text = args.join(' ');
  if (!text) {
    termWrite(`Usage: <span class="accent">score</span> &lt;policy_text&gt;`, 'stderr');
    return;
  }
  if (text.length < 20) {
    termWrite(`Text too short (min 20 chars).`, 'stderr');
    return;
  }
  if (!activeSector) {
    termWrite(`No active sector. Set one: <span class="accent">use &lt;sector_id&gt;</span>`, 'stderr');
    return;
  }
  termWrite(`  <span class="term-progress"></span> Scoring against ${escapeHtml(activeSector)} laws...`, 'info');
  showLoading('Scoring...');
  try {
    const form = new FormData();
    form.append('question', text);
    form.append('sector', activeSector);
    const r = await fetch(`${API}/api/admin/test`, { method: 'POST', body: form });
    const d = await r.json();
    const score = d?.result?.score || d?.score || d;
    const pct = score.compliance_percentage || score.score || 0;
    const total = score.total_requirements || 0;
    const met = score.met_requirements || 0;
    termWrite('', 'stdout');
    termWrite(`<span class="bold">Compliance Score [${escapeHtml(activeSector)}]</span>`, 'highlight');
    termWrite(`  Score: <span class="${pct >= 80 ? 'green' : pct >= 50 ? 'amber' : 'red'} bold">${pct}%</span>`, 'stdout');
    termWrite(`  Met:   ${met}/${total} requirements`, 'stdout');
    if (score.breakdown && score.breakdown.length) {
      termWrite(`<span class="dim">Breakdown:</span>`, 'info');
      for (const b of score.breakdown.slice(0, 10)) {
        const bCls = b.compliant ? 'green' : 'red';
        termWrite(`  <span class="${bCls}">${b.compliant ? '✓' : '✗'}</span> ${escapeHtml(b.requirement || b.name || '')}`, 'stdout');
      }
    }
  } catch (e) {
    termWrite(`<span class="red">✗</span> ${escapeHtml(e.message)}`, 'stderr');
  } finally {
    hideLoading();
  }
}

/* ═══════════════════════════════════════════
   COMMAND: agent (interactive mode)
   ═══════════════════════════════════════════ */

async function enterAgentMode() {
  _agentMode = true;
  _conversationHistory = [];
  setInput('ask a question (.. to exit)');
  const sectorLabel = activeSector ? escapeHtml(activeSector).padEnd(34) : 'All Sectors'.padEnd(34);
  const readyMsg = activeSector
    ? `Ask anything about ${escapeHtml(activeSector)} laws.`
    : `Ask anything across <span class="accent">all sectors</span>. Use <span class="accent">use &lt;sector&gt;</span> to narrow down.`;
  termWrite(`<span class="cyan">╔═══════════════════════════════════════════════╗
║   Agent Mode — ${sectorLabel}║
║   Ask compliance questions freely.              ║
║   Type <span class="amber">..</span> or <span class="amber">exit agent</span> to return to terminal.     ║
╚═══════════════════════════════════════════════╝</span>`, 'highlight');
  termWrite(`${termSpan('grac-agent>', 'cyan')} <span class="dim">${readyMsg}</span>`, 'info');
}

/* ═══════════════════════════════════════════
   COMMAND: load (multi-line paste mode)
   ═══════════════════════════════════════════ */

function enterLoadMode() {
  if (!activeSector) {
    termWrite(`No active sector. Set one first: <span class="accent">use &lt;sector_id&gt;</span>`, 'stderr');
    return;
  }
  _loadMode = true;
  _loadBuffer = [];
  setInput('paste text here (.. to finish)');
  termWrite(`<span class="purple">╔═══════════════════════════════════════════════╗
║   Paste Mode                                    ║
║   Paste or type your policy text (multi-line).  ║
║   Type <span class="amber">..</span> on its own line when done.            ║
║   Text will be analyzed against ${escapeHtml(activeSector).padEnd(28)}║
╚═══════════════════════════════════════════════╝</span>`, 'highlight');
}

/* ═══════════════════════════════════════════
   COMMAND: knowledge
   ═══════════════════════════════════════════ */

async function cmdKnowledge() {
  termWrite(`Fetching system knowledge...`, 'info');
  try {
    const r = await fetch(`${API}/api/system/knowledge`);
    const k = await r.json();
    termWrite(`
<span class="bold">System Knowledge</span>
<span class="dim">System:</span> ${escapeHtml(k.system_name)} v${escapeHtml(k.version)}
<span class="dim">Jurisdiction:</span> ${escapeHtml(k.jurisdiction)}
<span class="dim">Status:</span> ${k.status}

<span class="accent">Loaded Sectors:</span>`, 'stdout');
    for (const s of k.sectors || []) {
      const icon = s.is_ingested ? termSpan('READY', 'green') : termSpan('EMPTY', 'amber');
      const laws = s.loaded_laws.length
        ? s.loaded_laws.map(l => termSpan(escapeHtml(l), 'cyan')).join(', ')
        : '<span class="dim">No laws loaded</span>';
      termWrite(`  [${icon}] ${escapeHtml(s.sector_name)} <span class="dim">(${escapeHtml(s.sector_id)})</span> — ${laws}`, 'stdout');
    }
  } catch (e) {
    termWrite(`<span class="red">✗</span> ${escapeHtml(e.message)}`, 'stderr');
  }
}

/* ═══════════════════════════════════════════
   COMMAND: draft
   ═══════════════════════════════════════════ */

async function cmdDraft(args) {
  const topic = args.join(' ');
  const sector = activeSector || 'cybersecurity';
  if (!topic) {
    termWrite(`Usage: <span class="accent">draft</span> &lt;policy topic description&gt;`, 'stderr');
    termWrite(`Example: <span class="accent">draft</span> internal data breach response policy for financial institutions`, 'info');
    return;
  }
  termWrite(`  <span class="term-progress"></span> Generating policy draft for <span class="accent">${escapeHtml(topic)}</span>...`, 'info');
  showLoading('Drafting policy document...');
  try {
    const form = new FormData();
    form.append('topic', topic);
    form.append('sector', sector);
    const r = await fetch(`${API}/api/admin/draft`, { method: 'POST', body: form });
    const d = await r.json();
    termWrite('', 'stdout');
    if (d.status === 'ok') {
      termWrite(`<span class="bold">${escapeHtml(d.title)}</span>`, 'highlight');
      termWrite(`  File: <span class="cyan">${escapeHtml(d.filename)}</span>`, 'stdout');
      termWrite(`  <span class="green">✓</span> Download: <a href="${API}${d.download_url}" target="_blank" style="color:#4ade80;text-decoration:underline">${API}${d.download_url}</a>`, 'success');
    } else {
      termWrite(`<span class="red">✗</span> ${escapeHtml(d.detail || 'Draft generation failed')}`, 'stderr');
    }
  } catch (e) {
    termWrite(`<span class="red">✗</span> ${escapeHtml(e.message)}`, 'stderr');
  } finally {
    hideLoading();
  }
}

/* ═══════════════════════════════════════════
   COMMAND: clear
   ═══════════════════════════════════════════ */

function cmdClear() {
  document.getElementById('terminal-output').innerHTML = '';
}

/* ═══════════════════════════════════════════
   DASHBOARD / KNOWLEDGE Visual Views
   ═══════════════════════════════════════════ */

function loadDashboard() {
  const el = document.getElementById('view-dashboard');
  el.innerHTML = '<div class="admin-panel"><div class="spinner" style="margin:40px auto"></div></div>';
  fetch(`${API}/api/admin/sectors`)
    .then(r => r.json())
    .then(data => {
      const sectors = data.sectors || [];
      const total = sectors.length;
      const enabled = sectors.filter(s => s.enabled).length;
      const totalPdfs = sectors.reduce((s, sec) => s + sec.pdf_count, 0);
      const parsed = sectors.reduce((s, sec) => s + sec.parsed_count, 0);
      const ingested = sectors.filter(s => s.has_collection).length;
      el.innerHTML = `
        <div class="admin-panel">
          <h2>Dashboard</h2>
          <p class="subtitle">System overview</p>
          <div class="stats-grid">
            <div class="stat-card"><div class="stat-value">${total}</div><div class="stat-label">Sectors</div></div>
            <div class="stat-card"><div class="stat-value">${enabled}</div><div class="stat-label">Active</div></div>
            <div class="stat-card"><div class="stat-value">${totalPdfs}</div><div class="stat-label">PDFs</div></div>
            <div class="stat-card"><div class="stat-value">${parsed}</div><div class="stat-label">Parsed</div></div>
            <div class="stat-card"><div class="stat-value">${ingested}</div><div class="stat-label">Vectorized</div></div>
          </div>
          <div class="card">
            <div class="card-title">Sectors</div>
            <table>
              <tr><th>Sector</th><th>Status</th><th>PDFs</th><th>Parsed</th><th>Vector DB</th></tr>
              ${sectors.map(s => `
                <tr>
                  <td><strong>${escapeHtml(s.name)}</strong><br><span style="font-size:11px;color:var(--text-tertiary)">${escapeHtml(s.id)}</span></td>
                  <td>${s.enabled ? '<span class="badge badge-green">Active</span>' : '<span class="badge badge-red">Disabled</span>'}</td>
                  <td>${s.pdf_count}</td>
                  <td>${s.parsed_count}</td>
                  <td>${s.has_collection ? '<span class="badge badge-green">Ready</span>' : '<span class="badge badge-amber">Empty</span>'}</td>
                </tr>
              `).join('')}
            </table>
          </div>
        </div>`;
    })
    .catch(() => el.innerHTML = '<div class="admin-panel"><div class="error">Failed to load</div></div>');
}

function loadKnowledge() {
  const el = document.getElementById('view-knowledge');
  el.innerHTML = '<div class="admin-panel"><div class="spinner" style="margin:40px auto"></div></div>';
  fetch(`${API}/api/system/knowledge`)
    .then(r => r.json())
    .then(k => {
      const sectors = k.sectors || [];
      el.innerHTML = `
        <div class="admin-panel">
          <h2>System Knowledge</h2>
          <p class="subtitle">What the AI knows about itself</p>
          <div class="card">
            <div class="card-title">Self-Awareness Context</div>
            <div class="knowledge-block"><span class="hl">System:</span> ${escapeHtml(k.system_name)} (v${k.version})
<span class="hl">Jurisdiction:</span> ${escapeHtml(k.jurisdiction)}
<span class="hl">Status:</span> ${k.status}

<span class="hl">Loaded Sectors:</span>
${sectors.map(s => `  [${s.is_ingested ? '<span class="ok">READY</span>' : '<span class="empty">EMPTY</span>'}] ${s.sector_name} (${s.sector_id}): ${s.loaded_laws.length ? s.loaded_laws.join(', ') : '<span class="empty">No laws loaded</span>'}`).join('\n')}</div>
          </div>
          <div class="card">
            <div class="card-title">Sector Details</div>
            <table>
              <tr><th>Sector</th><th>Loaded Laws</th><th>Ingested</th></tr>
              ${sectors.map(s => `
                <tr>
                  <td><strong>${escapeHtml(s.sector_name)}</strong><br><span style="font-size:11px;color:var(--text-tertiary)">${escapeHtml(s.sector_id)}</span></td>
                  <td>${s.loaded_laws.length ? s.loaded_laws.join(', ') : '<span style="color:var(--text-tertiary)">None</span>'}</td>
                  <td>${s.is_ingested ? '<span class="badge badge-green">Ready</span>' : '<span class="badge badge-amber">Not ingested</span>'}</td>
                </tr>
              `).join('')}
            </table>
          </div>
        </div>`;
    })
    .catch(() => el.innerHTML = '<div class="admin-panel"><div class="error">Failed to load</div></div>');
}
