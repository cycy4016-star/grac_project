const App = {
  state: {
    messages: [],
    conversations: [],
    currentChatId: null,
    sector: 'cybersecurity',
    isProcessing: false,
    uploadedFile: null,
    sidebarOpen: false,
    currentTab: 'chat',
    analyzeFile: null,
    auditFile: null,
    kbFile: null,
    knowledgeOpen: false,
    isListening: false,
    voiceTimeout: null,
    voiceFinalText: '',
  },

  /* ---- Init ---- */
  init() {
    this.loadState();
    this.loadConversations();
    this.fetchSectorStatus();
    this.renderChatList();
    this.updateSectorBadge();
    document.getElementById('sector-select').value = this.state.sector;
    if (this.state.currentChatId) {
      const conv = this.getCurrentConversation();
      if (conv && conv.messages.length > 0) {
        this.state.messages = conv.messages;
        this.showChatView();
        this.renderMessages();
      } else {
        this.showWelcome();
      }
    } else {
      this.showWelcome();
    }
    this.loadKnowledgePanel();
  },

  /* ---- State Persistence ---- */
  saveState() {
    try { localStorage.setItem('grac_sector', this.state.sector); } catch (e) {}
    try { localStorage.setItem('grac_currentChatId', this.state.currentChatId || ''); } catch (e) {}
  },

  loadState() {
    try {
      const s = localStorage.getItem('grac_sector');
      if (s) this.state.sector = s;
      const cid = localStorage.getItem('grac_currentChatId');
      if (cid) this.state.currentChatId = cid;
    } catch (e) {}
  },

  /* ---- Conversations ---- */
  loadConversations() {
    try {
      const raw = localStorage.getItem('grac_conversations');
      this.state.conversations = raw ? JSON.parse(raw) : [];
    } catch (e) { this.state.conversations = []; }
  },

  saveConversations() {
    try {
      localStorage.setItem('grac_conversations', JSON.stringify(this.state.conversations.slice(0, 50)));
    } catch (e) {}
  },

  getCurrentConversation() {
    return this.state.conversations.find(c => c.id === this.state.currentChatId);
  },

  newChat() {
    this.state.currentChatId = null;
    this.state.messages = [];
    this.state.uploadedFile = null;
    this.state.analyzeFile = null;
    this.state.auditFile = null;
    this.saveState();
    this.showWelcome();
    document.getElementById('chat-messages').innerHTML = '';
    document.getElementById('chat-input').value = '';
    document.getElementById('send-btn').disabled = true;
    this.renderChatList();
    this.switchTab('chat');
    document.getElementById('chat-input').focus();
  },

  selectChat(chatId) {
    if (chatId === this.state.currentChatId) return;
    this.state.currentChatId = chatId;
    const conv = this.getCurrentConversation();
    if (conv) {
      this.state.messages = conv.messages || [];
      this.state.sector = conv.sector || this.state.sector;
      document.getElementById('sector-select').value = this.state.sector;
      this.updateSectorBadge();
    }
    this.saveState();
    this.showChatView();
    this.renderMessages();
    this.renderChatList();
    this.switchTab('chat');
    if (window.innerWidth <= 768) this.closeSidebar();
  },

  deleteChat(chatId, event) {
    event.stopPropagation();
    this.state.conversations = this.state.conversations.filter(c => c.id !== chatId);
    this.saveConversations();
    if (this.state.currentChatId === chatId) {
      this.newChat();
    } else {
      this.renderChatList();
    }
  },

  ensureConversation() {
    if (this.state.currentChatId) return this.state.currentChatId;
    const id = 'chat_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6);
    const title = this.state.messages.length > 0
      ? this.state.messages[0].text.slice(0, 60)
      : 'New conversation';
    this.state.currentChatId = id;
    this.state.conversations.unshift({
      id, title,
      sector: this.state.sector,
      messages: [],
      createdAt: new Date().toISOString(),
    });
    this.saveState();
    this.saveConversations();
    this.renderChatList();
    return id;
  },

  saveCurrentConversation() {
    const id = this.ensureConversation();
    const conv = this.state.conversations.find(c => c.id === id);
    if (conv) {
      conv.messages = this.state.messages.slice();
      conv.sector = this.state.sector;
      const firstUser = this.state.messages.find(m => m.role === 'user');
      if (firstUser) conv.title = firstUser.text.slice(0, 60);
      this.saveConversations();
      this.renderChatList();
    }
  },

  renderChatList() {
    const list = document.getElementById('chat-list');
    list.innerHTML = this.state.conversations.map(c =>
      `<div class="chat-item${c.id === this.state.currentChatId ? ' active' : ''}" onclick="App.selectChat('${c.id}')">
        <span class="chat-item-title">${this.escapeHtml(c.title || 'New conversation')}</span>
        <button class="chat-item-del" onclick="App.deleteChat('${c.id}', event)" title="Delete">✕</button>
      </div>`
    ).join('');
  },

  /* ---- View Switching ---- */
  showWelcome() {
    document.getElementById('welcome').style.display = 'flex';
    document.getElementById('chat-messages').style.display = 'none';
    document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
    document.getElementById('input-area').style.display = 'block';
  },

  showChatView() {
    document.getElementById('welcome').style.display = 'none';
    document.getElementById('chat-messages').style.display = 'flex';
    document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
    document.getElementById('input-area').style.display = 'block';
  },

  /* ---- Tabs ---- */
  switchTab(tab) {
    this.state.currentTab = tab;
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === tab);
    });

    const isChatTab = tab === 'chat';
    document.getElementById('input-area').style.display = isChatTab ? 'block' : 'none';
    document.getElementById('chat-messages').style.display = isChatTab && this.state.messages.length > 0 ? 'flex' : 'none';
    document.getElementById('welcome').style.display = isChatTab && this.state.messages.length === 0 ? 'flex' : 'none';

    document.querySelectorAll('.tab-content').forEach(el => {
      el.style.display = el.id === `tab-${tab}` ? 'block' : 'none';
    });

    this.updateTabSectorLabels();
    if (tab === 'knowledge') {
      this.renderKnowledgeTab();
    }
  },

  updateTabSectorLabels() {
    const label = this.sectorLabel();
    ['analyze-sector-label', 'draft-sector-label', 'audit-sector-label', 'kb-sector-label'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = label;
    });
  },

  sectorLabel() {
    const labels = {
      cybersecurity: 'Cybersecurity',
      fintech: 'Fintech',
      data_protection: 'Data Protection',
      healthcare: 'Healthcare',
    };
    return labels[this.state.sector] || this.state.sector;
  },

  /* ---- Knowledge Panel (slide-down) ---- */
  async toggleKnowledgePanel() {
    this.state.knowledgeOpen = !this.state.knowledgeOpen;
    const panel = document.getElementById('knowledge-panel');
    panel.style.display = this.state.knowledgeOpen ? 'block' : 'none';
    if (this.state.knowledgeOpen) {
      await this.loadKnowledgePanel();
    }
  },

  async loadKnowledgePanel() {
    const body = document.getElementById('knowledge-body');
    try {
      const resp = await fetch('/api/admin/sectors');
      const json = await resp.json();
      const sectors = json.sectors || [];
      body.innerHTML = sectors.map(s => {
        const badge = s.has_collection ? '<span class="status-badge ready">READY</span>'
          : s.pdf_count > 0 ? '<span class="status-badge missing">NOT INGESTED</span>'
          : '<span class="status-badge error">NO LAWS</span>';
        const lawNames = (s.laws || []).slice(0, 3).join(', ');
        const extra = (s.laws || []).length > 3 ? ` +${s.laws.length - 3} more` : '';
        return `<div class="kb-sector-mini">
          <div>
            <div class="name">${this.escapeHtml(s.name)}</div>
            <div class="laws">${this.escapeHtml(lawNames)}${extra}${!lawNames ? 'No laws configured' : ''}</div>
          </div>
          ${badge}
        </div>`;
      }).join('');
      if (sectors.length === 0) body.innerHTML = '<div style="padding:12px;font-size:0.78rem;color:var(--c-text-tertiary)">No sectors found.</div>';
    } catch (e) {
      body.innerHTML = '<div style="padding:12px;font-size:0.78rem;color:var(--c-danger)">Could not load knowledge.</div>';
    }
  },

  /* ---- Knowledge Tab ---- */
  async renderKnowledgeTab() {
    const listEl = document.getElementById('kb-sector-list');
    const ingestBtn = document.getElementById('kb-ingest-btn');
    ingestBtn.style.display = 'none';
    try {
      const resp = await fetch('/api/admin/sectors');
      const json = await resp.json();
      const sectors = json.sectors || [];
      listEl.innerHTML = sectors.map(s => {
        const statusDot = s.has_collection ? '✅' : s.pdf_count > 0 ? '⏳' : '📭';
        const pdfs = (s.pdfs || []).map(p => {
          const ingested = s.parsed_count > 0 ? 'ingested' : 'raw';
          return `<div class="kb-law-item">
            <div class="law-icon ${ingested}">${ingested === 'ingested' ? '✓' : 'PDF'}</div>
            <span class="law-name">${this.escapeHtml(p.name)}</span>
            <span class="law-status ${ingested}">${ingested}</span>
          </div>`;
        }).join('') || '<div class="kb-empty"><svg width="32" height="32" viewBox="0 0 24 24" fill="none"><path d="M12 16V4m0 0l-4 4m4-4l4 4M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg><p>No law files uploaded yet. Drop a PDF above.</p></div>';
        return `<div class="kb-sector-card">
          <div class="kb-sector-card-header">
            <span class="sector-name">${statusDot} ${this.escapeHtml(s.name)}</span>
            <span class="sector-meta">${s.pdf_count} PDFs · ${s.parsed_count} ingested</span>
          </div>
          <div class="kb-sector-card-body">${pdfs}</div>
        </div>`;
      }).join('');

      // Show ingest button if there are un-ingested PDFs
      const anyRaw = sectors.some(s => s.pdf_count > 0 && !s.has_collection);
      ingestBtn.style.display = anyRaw ? 'flex' : 'none';

    } catch (e) {
      listEl.innerHTML = '<div class="kb-empty"><p style="color:var(--c-danger)">Failed to load sectors.</p></div>';
    }
  },

  /* ---- Law File Upload (Knowledge tab) ---- */
  openLawUpload() {
    this.switchTab('knowledge');
    document.getElementById('kb-file-input').click();
  },

  handleLawFile(event) {
    const file = event.target.files[0];
    if (!file) return;
    if (!file.name.endsWith('.pdf')) {
      this.showToast('Only PDF files are supported for law upload.', 'error');
      return;
    }
    this.state.kbFile = file;
    const info = document.getElementById('kb-file-info');
    info.style.display = 'flex';
    info.innerHTML = `<span>📄 ${this.escapeHtml(file.name)}</span>
      <button class="tab-action-btn" style="padding:4px 12px;font-size:0.72rem" onclick="App.uploadLawFile()">Upload to ${this.sectorLabel()}</button>
      <button class="remove-file" onclick="App.clearLawFile()">✕</button>`;
    event.target.value = '';
  },

  clearLawFile() {
    this.state.kbFile = null;
    document.getElementById('kb-file-info').style.display = 'none';
  },

  dropLawFile(e) {
    e.preventDefault();
    e.currentTarget.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (!file) return;
    if (!file.name.endsWith('.pdf')) { this.showToast('Only PDF files are supported.', 'error'); return; }
    this.state.kbFile = file;
    const info = document.getElementById('kb-file-info');
    info.style.display = 'flex';
    info.innerHTML = `<span>📄 ${this.escapeHtml(file.name)}</span>
      <button class="tab-action-btn" style="padding:4px 12px;font-size:0.72rem" onclick="App.uploadLawFile()">Upload to ${this.sectorLabel()}</button>
      <button class="remove-file" onclick="App.clearLawFile()">✕</button>`;
  },

  async uploadLawFile() {
    const file = this.state.kbFile;
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    try {
      const resp = await fetch(`/api/admin/sectors/${this.state.sector}/upload`, { method: 'POST', body: formData });
      const json = await resp.json();
      if (!resp.ok) throw new Error(json.detail || 'Upload failed');
      this.showToast(`Uploaded ${file.name} to ${this.sectorLabel()}`, 'info');
      this.clearLawFile();
      this.renderKnowledgeTab();
      this.loadKnowledgePanel();
    } catch (e) {
      this.showToast(`Upload error: ${e.message}`, 'error');
    }
  },

  async runIngest() {
    const btn = document.getElementById('kb-ingest-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="tdot" style="animation:thinkBounce 1s infinite;display:inline-block;width:5px;height:5px;background:#fff;border-radius:50%"></span> Ingesting...';
    try {
      const resp = await fetch(`/api/admin/sectors/${this.state.sector}/ingest`, { method: 'POST' });
      const json = await resp.json();
      if (!resp.ok) throw new Error(json.detail || 'Ingestion failed');
      this.showToast(`Ingested ${json.pdfs_processed || 0} PDF(s)`, 'info');
      this.renderKnowledgeTab();
      this.loadKnowledgePanel();
    } catch (e) {
      this.showToast(`Ingestion error: ${e.message}`, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg> Ingest All Laws for This Sector';
    }
  },

  /* ---- Messages ---- */
  renderMessages() {
    const container = document.getElementById('chat-messages');
    container.innerHTML = this.state.messages.map((msg, i) => {
      if (msg.role === 'user') {
        const fileChip = msg.uploadedFile
          ? `<div class="file-chip">${this.escapeHtml(msg.uploadedFile)}</div>`
          : '';
        return `<div class="message user">
          <div class="message-avatar">U</div>
          <div class="message-body">
            ${fileChip}
            <div class="message-bubble">${this.escapeHtml(msg.text)}</div>
            <div class="message-time">${msg.time || ''}</div>
          </div>
        </div>`;
      } else {
        return this.renderAiMessage(msg, i);
      }
    }).join('');
    this.scrollToBottom();
  },

  renderAiMessage(msg, index) {
    const msgId = msg.id || `msg_${index}_${Date.now()}`;
    const parts = [];
    if (msg.uploadedFile) {
      parts.push(`<div class="file-chip">${this.escapeHtml(msg.uploadedFile)}</div>`);
    }
    parts.push(this.formatAnswer(msg.text));
    if (msg.summary) {
      parts.push(`<div class="message-bubble"><p><strong>Summary:</strong> ${this.escapeHtml(msg.summary)}</p></div>`);
    }
    if (msg.sources && msg.sources.length > 0) {
      parts.push(this.renderSources(msg.sources));
    }
    if (msg.score) {
      parts.push(this.renderScore(msg.score));
    }
    if (msg.gaps && msg.gaps.length > 0) {
      parts.push(this.renderGaps(msg.gaps));
    }
    if (msg.draftUrl) {
      parts.push(this.renderDraftBanner(msg.draftUrl));
    }
    const feedback = this.renderFeedback(msgId, msg);
    return `<div class="message ai" data-msg-id="${msgId}">
      <div class="message-avatar">G</div>
      <div class="message-body">${parts.join('')}
        ${feedback}
        <div class="message-time">${msg.time || ''}</div>
      </div>
    </div>`;
  },

  renderFeedback(msgId, msg) {
    return `<div class="message-feedback">
      <button class="feedback-btn" onclick="App.rateMessage('${msgId}', 2)" title="Helpful" id="fb-up-${msgId}">👍</button>
      <button class="feedback-btn" onclick="App.rateMessage('${msgId}', 1)" title="Needs improvement" id="fb-down-${msgId}">👎</button>
      <button class="feedback-correction-toggle" onclick="App.toggleCorrection('${msgId}')">Suggest correction</button>
      <div class="feedback-correction-box" id="fb-correction-${msgId}">
        <textarea placeholder="What should the correct answer have been?" id="fb-text-${msgId}"></textarea>
        <button class="submit-correction" onclick="App.submitCorrection('${msgId}')">Submit</button>
      </div>
    </div>`;
  },

  async rateMessage(msgId, rating) {
    const upBtn = document.getElementById(`fb-up-${msgId}`);
    const downBtn = document.getElementById(`fb-down-${msgId}`);
    upBtn.classList.toggle('active', rating === 2);
    downBtn.classList.toggle('active', rating === 1);

    const msgEl = document.querySelector(`[data-msg-id="${msgId}"]`);
    const msgIndex = Array.from(document.querySelectorAll('.message.ai')).indexOf(msgEl);
    const msg = this.state.messages.filter(m => m.role === 'assistant')[msgIndex];
    if (!msg) return;

    const userMsg = this.state.messages[this.state.messages.indexOf(msg) - 1];
    if (!userMsg) return;

    try {
      await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message_id: msgId,
          question: userMsg.text || '',
          answer: msg.text || '',
          rating,
          sector: this.state.sector,
          sources: msg.sources || [],
        }),
      });
    } catch (e) {
      console.error('Feedback save failed', e);
    }
  },

  toggleCorrection(msgId) {
    const box = document.getElementById(`fb-correction-${msgId}`);
    box.classList.toggle('visible');
  },

  async submitCorrection(msgId) {
    const textarea = document.getElementById(`fb-text-${msgId}`);
    const correction = textarea.value.trim();
    if (!correction) { this.showToast('Please write your correction.', 'error'); return; }

    const msgEl = document.querySelector(`[data-msg-id="${msgId}"]`);
    const msgIndex = Array.from(document.querySelectorAll('.message.ai')).indexOf(msgEl);
    const msg = this.state.messages.filter(m => m.role === 'assistant')[msgIndex];
    if (!msg) return;
    const userMsg = this.state.messages[this.state.messages.indexOf(msg) - 1];
    if (!userMsg) return;

    try {
      await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message_id: msgId,
          question: userMsg.text || '',
          answer: msg.text || '',
          rating: 1,
          correction,
          sector: this.state.sector,
          sources: msg.sources || [],
        }),
      });
      textarea.value = '';
      document.getElementById(`fb-correction-${msgId}`).classList.remove('visible');
      this.showToast('Correction submitted — helps the system learn!', 'info');
    } catch (e) {
      this.showToast('Failed to submit correction.', 'error');
    }
  },

  addMessage(msg) {
    this.state.messages.push(msg);
    this.saveCurrentConversation();
    this.showChatView();
    this.renderMessages();
  },

  /* ---- Formatting ---- */
  formatAnswer(text) {
    if (!text) return '<div class="message-bubble">No response.</div>';
    const lines = text.split('\n');
    let html = '<div class="message-bubble">';
    let inList = false;
    for (const line of lines) {
      const t = line.trim();
      if (!t) {
        if (inList) { html += '</ul>'; inList = false; }
        html += '<p></p>';
        continue;
      }
      if (t.startsWith('- ') || t.startsWith('• ')) {
        if (!inList) { html += '<ul>'; inList = true; }
        html += `<li>${this.inlineMarkup(t.slice(2))}</li>`;
        continue;
      }
      if (/^\d+[.)]\s/.test(t)) {
        const num = t.match(/^\d+[.)]/)[0];
        const content = t.replace(/^\d+[.)]\s/, '');
        if (inList) { html += '</ul>'; inList = false; }
        html += `<p><strong>${num}</strong> ${this.inlineMarkup(content)}</p>`;
        continue;
      }
      if (inList) { html += '</ul>'; inList = false; }
      if (t.startsWith('**') && t.endsWith('**')) {
        html += `<p><strong>${this.escapeHtml(t.slice(2, -2))}</strong></p>`;
      } else {
        html += `<p>${this.inlineMarkup(t)}</p>`;
      }
    }
    if (inList) html += '</ul>';
    html += '</div>';
    return html;
  },

  inlineMarkup(text) {
    let s = this.escapeHtml(text);
    s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/\*(.+?)\*/g, '<em>$1</em>');
    s = s.replace(/`(.+?)`/g, '<code>$1</code>');
    return s;
  },

  renderSources(sources) {
    if (!sources || sources.length === 0) return '';
    const tags = sources.map(s => {
      const label = s.law_name || s.title || 'Source';
      const title = s.section_number ? `${label} §${s.section_number}` : label;
      return `<span class="source-tag" title="${this.escapeHtml(s.text || s.snippet || '')}">${this.escapeHtml(title)}</span>`;
    }).join('');
    return `<div class="sources">${tags}</div>`;
  },

  renderScore(score) {
    const pct = score.percentage || 0;
    const grade = score.grade || 'F';
    const barColor = { A: '#22c55e', B: '#16a34a', C: '#f59e0b', D: '#f97316', F: '#ef4444' }[grade] || '#94a3b8';
    const breakdown = score.breakdown || {};
    const items = ['critical', 'high', 'medium', 'low'].map(sev => {
      const b = breakdown[sev] || { count: 0 };
      return `<div class="score-breakdown-item ${sev}"><span class="count">${b.count}</span>${sev}</div>`;
    }).join('');
    return `<div class="score-card">
      <div class="score-header">
        <div class="score-grade ${grade}">${grade}</div>
        <div class="score-percentage">${pct}%</div>
      </div>
      <div class="score-bar"><div class="score-bar-fill" style="width:${pct}%;background:${barColor}"></div></div>
      <div class="score-breakdown">${items}</div>
    </div>`;
  },

  renderGaps(gaps) {
    if (!gaps || gaps.length === 0) return '';
    return gaps.map(g => {
      const sev = (g.severity || 'medium').toLowerCase();
      return `<div class="gap-item">
        <div class="gap-header">
          <span class="gap-severity ${sev}">${sev}</span>
          <span class="gap-law">${this.escapeHtml(g.law_reference || '')}</span>
        </div>
        <div class="gap-req">${this.escapeHtml(g.requirement || '')}</div>
        <div class="gap-rec">${this.escapeHtml(g.recommendation || '')}</div>
      </div>`;
    }).join('');
  },

  renderDraftBanner(url) {
    return `<div class="draft-banner">
      <span>📄 Policy draft generated</span>
      <a href="${url}" class="draft-link" target="_blank">Download PDF</a>
    </div>`;
  },

  /* ---- Sending Messages (Chat tab) ---- */
  async sendMessage() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if ((!text && !this.state.uploadedFile) || this.state.isProcessing) return;

    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    if (this.state.uploadedFile) {
      const file = this.state.uploadedFile;
      this.addMessage({ role: 'user', text: text || `Analyze this document: ${file.name}`, time, uploadedFile: file.name });
      input.value = '';
      document.getElementById('send-btn').disabled = true;
      this.state.isProcessing = true;
      this.startThinking('analyze');
      try {
        await this.runDocumentAnalyze(file, text, time);
      } catch (err) {
        this.addMessage({ role: 'assistant', text: `Error: ${err.message || 'Request failed.'}`, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) });
      } finally {
        this.state.isProcessing = false;
        this.state.uploadedFile = null;
      }
      return;
    }

    this.addMessage({ role: 'user', text, time });
    input.value = '';
    document.getElementById('send-btn').disabled = true;
    this.state.isProcessing = true;
    this.startThinking('chat');

    try {
      await this.sendComplianceQuery(text, time);
    } catch (err) {
      this.addMessage({ role: 'assistant', text: `Error: ${err.message || 'Request failed. Please try again.'}`, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) });
    } finally {
      this.state.isProcessing = false;
    }
  },

  async sendComplianceQuery(question, time) {
    // Build conversation history for context
    const recentMessages = this.state.messages.slice(-10).map(m => ({
      role: m.role,
      content: m.text,
    }));
    const resp = await fetch('/api/general', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: question,
        history: JSON.stringify(recentMessages),
      }),
    });
    const json = await resp.json();
    this.stopThinking();
    if (!resp.ok) throw new Error(json.detail || `HTTP ${resp.status}`);
    const data = json.data || json;
    const answer = data.answer || data.result?.answer || '';
    const sources = data.sources || data.result?.sources || [];
    const scoreData = data.score || (data.result && data.result.score) || null;
    const score = scoreData && scoreData.percentage ? { percentage: scoreData.percentage, grade: scoreData.grade, breakdown: scoreData.breakdown } : null;
    const draftUrl = data.draft_url || (data.result && data.result.draft_url) || '';
    const gaps = data.steps?.analysis?.gaps || data.result?.steps?.analysis?.gaps || [];

    // Handle auto-sector switch
    if (data.sector_switched && data.sector_switch_note) {
      this.state.sector = data.sector_detected;
      this.saveState();
      this.updateSectorBadge();
      this.updateTabSectorLabels();
      this.fetchSectorStatus();
      this.loadKnowledgePanel();
      this.showToast(data.sector_switch_note, 'info');
    }

    // Prepend sector switch note to answer
    let finalAnswer = answer;
    if (data.sector_switched && data.sector_switch_note) {
      finalAnswer = `*${data.sector_switch_note}*\n\n${answer}`;
    }
    this.addMessage({ role: 'assistant', text: finalAnswer, sources, score, gaps, draftUrl, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) });
  },

  async runDocumentAnalyze(file, note, time) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('sector', this.state.sector);
    formData.append('output_format', 'pdf');
    const resp = await fetch('/api/analyze-document', { method: 'POST', body: formData });
    const json = await resp.json();
    this.stopThinking();
    if (!resp.ok) throw new Error(json.detail || `HTTP ${resp.status}`);
    const data = json.data || json;
    const steps = data.steps || {};
    const analysis = steps.analysis || data.analysis || {};
    const scoreData = steps.score || data.score || {};
    const docData = steps.document || data.document || {};
    const answer = analysis.summary || 'Analysis complete.';
    const gaps = analysis.gaps || [];
    const score = scoreData.percentage ? { percentage: scoreData.percentage, grade: scoreData.grade, breakdown: scoreData.breakdown } : null;
    const draftUrl = docData.path ? `/api/download/${docData.path.split('/').pop()}` : '';
    this.addMessage({
      role: 'assistant', text: answer, sources: [], score, gaps, draftUrl,
      summary: `Analyzed ${file.name} against ${this.state.sector} laws.`,
      uploadedFile: file.name,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    });
  },

  /* ---- Analyze Tab ---- */
  handleAnalyzeFile(event) {
    const file = event.target.files[0];
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'docx', 'txt'].includes(ext)) { this.showToast('Unsupported file format.', 'error'); return; }
    this.state.analyzeFile = file;
    document.getElementById('analyze-file-info').style.display = 'flex';
    document.getElementById('analyze-file-info').innerHTML =
      `<span>📄 ${this.escapeHtml(file.name)}</span>
       <button class="remove-file" onclick="App.clearAnalyzeFile()">✕</button>`;
    event.target.value = '';
  },

  clearAnalyzeFile() {
    this.state.analyzeFile = null;
    document.getElementById('analyze-file-info').style.display = 'none';
  },

  async runAnalyze() {
    const text = document.getElementById('analyze-text').value.trim();
    const file = this.state.analyzeFile;
    if (!text && !file) { this.showToast('Please upload a file or paste text.', 'error'); return; }
    if (this.state.isProcessing) return;
    this.state.isProcessing = true;
    this.startThinking('analyze');
    this.switchTab('chat');
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    try {
      if (file) {
        this.addMessage({ role: 'user', text: text || `Analyze this document: ${file.name}`, time, uploadedFile: file.name });
        await this.runDocumentAnalyze(file, text, time);
        this.clearAnalyzeFile();
        document.getElementById('analyze-text').value = '';
      } else {
        this.addMessage({ role: 'user', text: text, time });
        const resp = await fetch('/api/analyze-policy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ policy: text, sector: this.state.sector, output_format: 'pdf' }),
        });
        const json = await resp.json();
        this.stopThinking();
        if (!resp.ok) throw new Error(json.detail || `HTTP ${resp.status}`);
        const data = json.data || json;
        const steps = data.steps || {};
        const analysis = steps.analysis || data.analysis || {};
        const scoreData = steps.score || data.score || {};
        const docData = steps.document || data.document || {};
        const gaps = analysis.gaps || [];
        const score = scoreData.percentage ? { percentage: scoreData.percentage, grade: scoreData.grade, breakdown: scoreData.breakdown } : null;
        const draftUrl = docData.path ? `/api/download/${docData.path.split('/').pop()}` : '';
        this.addMessage({
          role: 'assistant', text: analysis.summary || 'Analysis complete.', sources: [], score, gaps, draftUrl,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        });
        document.getElementById('analyze-text').value = '';
      }
    } catch (err) {
      this.addMessage({ role: 'assistant', text: `Error: ${err.message || 'Analysis failed.'}`, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) });
    } finally {
      this.state.isProcessing = false;
    }
  },

  /* ---- Draft Tab ---- */
  async runDraft() {
    const topic = document.getElementById('draft-topic').value.trim();
    if (!topic) { this.showToast('Please describe the policy you want drafted.', 'error'); return; }
    if (this.state.isProcessing) return;
    this.state.isProcessing = true;
    this.startThinking('draft');
    this.switchTab('chat');
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    this.addMessage({ role: 'user', text: `Draft a policy: ${topic}`, time });

    try {
      const resp = await fetch('/api/draft-policy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, sector: this.state.sector }),
      });
      const json = await resp.json();
      this.stopThinking();
      if (!resp.ok) throw new Error(json.detail || `HTTP ${resp.status}`);
      const data = json.data || json;
      const answer = data.title ? `Policy draft generated: **${data.title}**` : 'Policy draft generated.';
      const draftUrl = data.download_url || data.result?.download_url || '';
      this.addMessage({ role: 'assistant', text: answer, draftUrl, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) });
      document.getElementById('draft-topic').value = '';
    } catch (err) {
      this.addMessage({ role: 'assistant', text: `Error: ${err.message || 'Draft failed.'}`, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) });
    } finally {
      this.state.isProcessing = false;
    }
  },

  /* ---- Audit Tab ---- */
  handleAuditFile(event) {
    const file = event.target.files[0];
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'docx', 'txt'].includes(ext)) { this.showToast('Unsupported file format.', 'error'); return; }
    this.state.auditFile = file;
    document.getElementById('audit-file-info').style.display = 'flex';
    document.getElementById('audit-file-info').innerHTML =
      `<span>📄 ${this.escapeHtml(file.name)}</span>
       <button class="remove-file" onclick="App.clearAuditFile()">✕</button>`;
    event.target.value = '';
  },

  clearAuditFile() {
    this.state.auditFile = null;
    document.getElementById('audit-file-info').style.display = 'none';
  },

  async runAudit() {
    const text = document.getElementById('audit-text').value.trim();
    const file = this.state.auditFile;
    if (!text && !file) { this.showToast('Please upload a file or paste text.', 'error'); return; }
    if (this.state.isProcessing) return;
    this.state.isProcessing = true;
    this.startThinking('audit');
    this.switchTab('chat');
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    try {
      if (file) {
        this.addMessage({ role: 'user', text: text || `Full audit of: ${file.name}`, time, uploadedFile: file.name });
        const formData = new FormData();
        formData.append('file', file);
        formData.append('sector', this.state.sector);
        formData.append('output_format', 'pdf');
        const resp = await fetch('/api/analyze-document', { method: 'POST', body: formData });
        const json = await resp.json();
        this.stopThinking();
        if (!resp.ok) throw new Error(json.detail || `HTTP ${resp.status}`);
        const data = json.data || json;
        const steps = data.steps || {};
        const analysis = steps.analysis || data.analysis || {};
        const scoreData = steps.score || data.score || {};
        const score = scoreData.percentage ? { percentage: scoreData.percentage, grade: scoreData.grade, breakdown: scoreData.breakdown } : null;
        const docData = steps.document || data.document || {};
        const draftUrl = docData.path ? `/api/download/${docData.path.split('/').pop()}` : '';
        this.addMessage({ role: 'assistant', text: analysis.summary || 'Audit complete.', sources: [],
          score, gaps: analysis.gaps || [], draftUrl,
          summary: `Full compliance audit of ${file.name} against ${this.state.sector} laws.`,
          uploadedFile: file.name, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) });
        this.clearAuditFile();
        document.getElementById('audit-text').value = '';
      } else {
        this.addMessage({ role: 'user', text: text, time });
        const resp = await fetch('/api/analyze-policy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ policy: text, sector: this.state.sector, output_format: 'pdf' }),
        });
        const json = await resp.json();
        this.stopThinking();
        if (!resp.ok) throw new Error(json.detail || `HTTP ${resp.status}`);
        const data = json.data || json;
        const steps = data.steps || {};
        const analysis = steps.analysis || data.analysis || {};
        const scoreData = steps.score || data.score || {};
        const score = scoreData.percentage ? { percentage: scoreData.percentage, grade: scoreData.grade, breakdown: scoreData.breakdown } : null;
        const docData = steps.document || data.document || {};
        const draftUrl = docData.path ? `/api/download/${docData.path.split('/').pop()}` : '';
        this.addMessage({ role: 'assistant', text: analysis.summary || 'Audit complete.', sources: [],
          score, gaps: analysis.gaps || [], draftUrl, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) });
        document.getElementById('audit-text').value = '';
      }
    } catch (err) {
      this.addMessage({ role: 'assistant', text: `Error: ${err.message || 'Audit failed.'}`, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) });
    } finally {
      this.state.isProcessing = false;
    }
  },

  /* ---- File Upload (Chat tab) ---- */
  triggerFileUpload() { document.getElementById('file-input').click(); },

  handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'docx', 'txt'].includes(ext)) { this.showToast('Unsupported format. Use PDF, DOCX, or TXT.', 'error'); return; }
    this.state.uploadedFile = file;
    this.showToast(`Attached: ${file.name}`, 'info');
    document.getElementById('chat-input').placeholder = 'Add a note or just send to analyze...';
    document.getElementById('chat-input').focus();
    event.target.value = '';
  },

  dragOver(e) { e.preventDefault(); if (e.currentTarget) e.currentTarget.classList.add('dragover'); },
  dragLeave(e) { e.preventDefault(); if (e.currentTarget) e.currentTarget.classList.remove('dragover'); },
  dropAnalyzeFile(e) {
    e.preventDefault(); e.currentTarget.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'docx', 'txt'].includes(ext)) { this.showToast('Unsupported format.', 'error'); return; }
    this.state.analyzeFile = file;
    document.getElementById('analyze-file-info').style.display = 'flex';
    document.getElementById('analyze-file-info').innerHTML = `<span>📄 ${this.escapeHtml(file.name)}</span><button class="remove-file" onclick="App.clearAnalyzeFile()">✕</button>`;
  },
  dropAuditFile(e) {
    e.preventDefault(); e.currentTarget.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'docx', 'txt'].includes(ext)) { this.showToast('Unsupported format.', 'error'); return; }
    this.state.auditFile = file;
    document.getElementById('audit-file-info').style.display = 'flex';
    document.getElementById('audit-file-info').innerHTML = `<span>📄 ${this.escapeHtml(file.name)}</span><button class="remove-file" onclick="App.clearAuditFile()">✕</button>`;
  },

  /* ---- Sector ---- */
  async switchSector(sector) {
    if (sector === this.state.sector) return;
    this.state.sector = sector;
    this.saveState();
    this.updateSectorBadge();
    this.updateTabSectorLabels();
    this.fetchSectorStatus();
    this.loadKnowledgePanel();
    this.showToast(`Switched to ${this.sectorLabel()}`, 'info');
  },

  updateSectorBadge() {
    document.getElementById('topbar-sector-badge').textContent = this.sectorLabel();
    document.getElementById('sector-select').value = this.state.sector;
  },

  async fetchSectorStatus() {
    const statusEl = document.getElementById('sector-status');
    const lawsEl = document.getElementById('sector-laws');
    try {
      const resp = await fetch('/api/system/knowledge');
      const json = await resp.json();
      const sectors = json.sectors || [];
      const current = sectors.find(s => s.sector_id === this.state.sector);
      if (current) {
        const dot = statusEl.querySelector('.status-dot');
        const text = statusEl.querySelector('.status-text');
        dot.className = 'status-dot' + (current.is_ingested ? '' : ' loading');
        text.textContent = current.is_ingested ? 'Ready' : 'Not ingested';
        const lawNames = current.loaded_laws || [];
        lawsEl.textContent = lawNames.length > 0 ? `Laws: ${lawNames.join(', ')}` : 'No laws loaded yet';
      } else {
        statusEl.querySelector('.status-dot').className = 'status-dot error';
        statusEl.querySelector('.status-text').textContent = 'Unknown';
      }
    } catch (e) {
      statusEl.querySelector('.status-dot').className = 'status-dot error';
      statusEl.querySelector('.status-text').textContent = 'Offline';
    }
  },

  /* ---- Thinking Companion ---- */
  thinkingSteps: {
    chat: [
      { text: 'Consulting {sector} regulations...', icon: '📜' },
      { text: 'Cross-referencing relevant laws...', icon: '🔍' },
      { text: 'Analyzing against compliance framework...', icon: '⚖️' },
      { text: 'Formulating your response...', icon: '✍️' },
    ],
    analyze: [
      { text: 'Reading document contents...', icon: '📖' },
      { text: 'Extracting policy provisions...', icon: '🔎' },
      { text: 'Mapping against {sector} legal requirements...', icon: '🔄' },
      { text: 'Identifying compliance gaps...', icon: '⚠️' },
      { text: 'Calculating compliance score...', icon: '📊' },
    ],
    draft: [
      { text: 'Researching {sector} regulatory requirements...', icon: '📚' },
      { text: 'Structuring policy document...', icon: '📐' },
      { text: 'Drafting aligned provisions...', icon: '✍️' },
      { text: 'Verifying legal soundness...', icon: '✅' },
    ],
    audit: [
      { text: 'Preparing audit framework...', icon: '📋' },
      { text: 'Scrutinizing controls against {sector} laws...', icon: '🔬' },
      { text: 'Evaluating compliance posture...', icon: '📏' },
      { text: 'Quantifying risk exposure...', icon: '📈' },
      { text: 'Generating audit findings...', icon: '📝' },
    ],
  },

  startThinking(type) {
    const el = document.getElementById('thinking-indicator');
    const stepsEl = document.getElementById('thinking-steps');
    const statusEl = document.getElementById('thinking-status');
    const sector = this.sectorLabel();
    el.style.display = 'block';
    statusEl.textContent = 'Working...';
    const steps = (this.thinkingSteps[type] || this.thinkingSteps.chat).map(s => ({
      ...s,
      text: s.text.replace('{sector}', sector),
    }));
    stepsEl.innerHTML = steps.map((s, i) =>
      `<div class="thinking-step ${i === 0 ? 'active' : 'pending'}" data-step="${i}">
        <div class="step-icon">${i === 0 ? '' : s.icon}</div>
        <span class="step-text">${s.text}</span>
        <span class="step-check">✓</span>
      </div>`
    ).join('');
    this._thinkTimer = 1;
    this._thinkInterval = setInterval(() => {
      const current = this._thinkTimer;
      const total = steps.length;
      if (current >= total) { statusEl.textContent = 'Finalizing...'; return; }
      stepsEl.querySelectorAll('.thinking-step').forEach((el, i) => {
        el.className = 'thinking-step';
        if (i < current) el.classList.add('done');
        else if (i === current) el.classList.add('active');
        else el.classList.add('pending');
        const iconEl = el.querySelector('.step-icon');
        if (i <= current) iconEl.textContent = steps[i].icon;
      });
      statusEl.textContent = steps[current]?.text || 'Working...';
      this._thinkTimer++;
    }, 1200);
    this.scrollToBottom();
  },

  stopThinking() {
    clearInterval(this._thinkInterval);
    document.getElementById('thinking-indicator').style.display = 'none';
    document.getElementById('thinking-steps').innerHTML = '';
  },

  /* ---- Voice Input ---- */
  toggleVoice() {
    if (this.state.isListening) {
      this.stopVoice();
    } else {
      this.startVoice();
    }
  },

  startVoice() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      this.showToast('Voice input is not supported in this browser. Try Chrome or Edge.', 'error');
      return;
    }

    this.state.isListening = true;
    document.getElementById('voice-btn').classList.add('active');
    document.getElementById('voice-waveform').style.display = 'flex';
    document.getElementById('voice-status-text').textContent = 'Listening...';
    document.getElementById('chat-input').placeholder = 'Speak now...';

    this.state.voiceFinalText = '';

    try {
      this._recognition = new SpeechRecognition();
      this._recognition.continuous = true;
      this._recognition.interimResults = true;
      this._recognition.lang = 'en-US';

      this._recognition.onresult = (event) => {
        let interim = '';
        let final = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          if (result.isFinal) {
            final += result[0].transcript;
          } else {
            interim += result[0].transcript;
          }
        }

        const displayText = final + interim;
        const input = document.getElementById('chat-input');
        input.value = displayText;
        this.state.voiceFinalText = final || this.state.voiceFinalText;
        this.onInputChange();

        // Reset silence timeout
        if (this.state.voiceTimeout) clearTimeout(this.state.voiceTimeout);
        this.state.voiceTimeout = setTimeout(() => {
          this.autoSubmitVoice();
        }, 1500);
      };

      this._recognition.onerror = (event) => {
        if (event.error === 'no-speech') return;
        this.showToast(`Voice error: ${event.error}`, 'error');
        this.stopVoice();
      };

      this._recognition.onend = () => {
        // If still in listening mode, restart (continuous)
        if (this.state.isListening) {
          try { this._recognition.start(); } catch (e) {}
        }
      };

      this._recognition.start();
    } catch (e) {
      this.showToast('Failed to start voice recognition.', 'error');
      this.stopVoice();
    }
  },

  stopVoice() {
    this.state.isListening = false;
    if (this.state.voiceTimeout) {
      clearTimeout(this.state.voiceTimeout);
      this.state.voiceTimeout = null;
    }
    if (this._recognition) {
      try { this._recognition.stop(); } catch (e) {}
      this._recognition = null;
    }
    document.getElementById('voice-btn').classList.remove('active');
    document.getElementById('voice-waveform').style.display = 'none';
    if (!document.getElementById('chat-input').value.trim()) {
      document.getElementById('chat-input').placeholder = 'Ask a compliance question...';
    }
  },

  autoSubmitVoice() {
    const text = document.getElementById('chat-input').value.trim();
    this.stopVoice();
    if (text) {
      this.showToast('Voice captured — processing...', 'info');
      this.sendMessage();
    }
  },

  handleKey(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  },

  onInputChange() {
    const input = document.getElementById('chat-input');
    const btn = document.getElementById('send-btn');
    btn.disabled = input.value.trim() === '' && !this.state.uploadedFile;
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 150) + 'px';
  },

  scrollToBottom() {
    const area = document.getElementById('content-area');
    setTimeout(() => { area.scrollTop = area.scrollHeight; }, 50);
  },

  showToast(message, type) {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();
    const toast = document.createElement('div');
    toast.className = `toast ${type || 'info'}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  },

  escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  },
};

document.addEventListener('DOMContentLoaded', () => App.init());
