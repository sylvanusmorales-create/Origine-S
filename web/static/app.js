marked.setOptions({ breaks: true, gfm: true });
hljs.configure({ ignoreUndetectedLanguage: true });

const $ = id => document.getElementById(id);
const messagesEl = $('messages');
const inputEl = $('input');
const convListEl = $('conv-list');
const chatTitleEl = $('chat-title');
const statusDot = $('status-dot');
const suggestionsBar = $('suggestions-bar');
const thinkingBar = $('thinking-bar');
const dropzoneOverlay = $('dropzone-overlay');

let currentConvId = null;
let ws = null;
let isStreaming = false;
let autoScroll = true;
let currentAssistantBubble = null;
let currentAssistantText = '';
let currentToolEl = null;
let allConversations = [];
let recognition = null;

// ━━ Conversations ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async function loadConversations(filter = '') {
    const res = await fetch('/api/conversations');
    allConversations = await res.json();
    renderConversations(filter);
}

function renderConversations(filter = '') {
    convListEl.innerHTML = '';
    const filtered = filter
        ? allConversations.filter(c => c.title.toLowerCase().includes(filter.toLowerCase()))
        : allConversations;
    filtered.forEach(c => {
        const el = document.createElement('div');
        el.className = 'conv-item' + (c.id === currentConvId ? ' active' : '');
        el.textContent = c.title;
        el.dataset.id = c.id;
        el.addEventListener('click', () => openConversation(c.id));
        convListEl.appendChild(el);
    });
}

async function openConversation(convId) {
    if (isStreaming) return;
    currentConvId = convId;
    messagesEl.innerHTML = '';
    chatTitleEl.textContent = '...';
    hideSuggestions();

    const [conv, msgs] = await Promise.all([
        fetch(`/api/conversations/${convId}`).then(r => r.json()),
        fetch(`/api/conversations/${convId}/messages`).then(r => r.json())
    ]);

    chatTitleEl.textContent = conv.title;
    msgs.forEach(m => appendMessage(m.role, m.content, m.id));
    scrollToBottom(true);
    connectWS(convId);
    renderConversations($('search-input').value);
    if (msgs.length >= 2) loadSuggestions(convId);
}

async function newConversation() {
    if (isStreaming) return;
    const conv = await fetch('/api/conversations', { method: 'POST' }).then(r => r.json());
    showWelcome();
    chatTitleEl.textContent = 'Nouvelle conversation';
    currentConvId = conv.id;
    hideSuggestions();
    connectWS(conv.id);
    allConversations.unshift(conv);
    renderConversations($('search-input').value);
}

async function deleteConversation() {
    if (!currentConvId) return;
    if (!confirm('Supprimer cette conversation ?')) return;
    await fetch(`/api/conversations/${currentConvId}`, { method: 'DELETE' });
    currentConvId = null;
    ws && ws.close(); ws = null;
    showWelcome();
    chatTitleEl.textContent = 'Nouvelle conversation';
    hideSuggestions();
    loadConversations($('search-input').value);
}

async function renameConversation() {
    if (!currentConvId) return;
    const title = prompt('Nouveau nom :', chatTitleEl.textContent);
    if (!title?.trim()) return;
    await fetch(`/api/conversations/${currentConvId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title.trim() })
    });
    chatTitleEl.textContent = title.trim();
    const idx = allConversations.findIndex(c => c.id === currentConvId);
    if (idx >= 0) allConversations[idx].title = title.trim();
    renderConversations($('search-input').value);
}

// ━━ WebSocket ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function connectWS(convId) {
    if (ws) ws.close();
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${proto}://${location.host}/ws/${convId}`);
    ws.onopen = () => statusDot.classList.add('online');
    ws.onclose = () => {
        statusDot.classList.remove('online');
        setTimeout(() => { if (currentConvId === convId) connectWS(convId); }, 3000);
    };
    ws.onerror = () => ws.close();
    ws.onmessage = e => handleWSEvent(JSON.parse(e.data));
}

function handleWSEvent(data) {
    switch (data.type) {
        case 'tool_start':
            showTool(data.name, data.input);
            break;
        case 'tool_end':
            hideTool();
            break;
        case 'token':
            if (!currentAssistantBubble) {
                hideThinking();
                startAssistantBubble();
            }
            currentAssistantText += data.content;
            renderStreaming(currentAssistantText);
            if (autoScroll) scrollToBottom();
            break;
        case 'done':
            finalizeAssistant(data.msg_id);
            setStreaming(false);
            if (currentConvId) loadSuggestions(currentConvId);
            break;
        case 'stopped':
            if (currentAssistantBubble) {
                currentAssistantBubble.querySelector('.cursor')?.remove();
                addActions(currentAssistantBubble.closest('.msg'));
            }
            currentAssistantBubble = null;
            currentAssistantText = '';
            setStreaming(false);
            break;
        case 'title':
            if (data.conv_id === currentConvId) {
                chatTitleEl.textContent = data.title;
                const idx = allConversations.findIndex(c => c.id === data.conv_id);
                if (idx >= 0) allConversations[idx].title = data.title;
                renderConversations($('search-input').value);
            }
            break;
        case 'error':
            hideThinking();
            showError(data.message);
            setStreaming(false);
            break;
    }
}

// ━━ Messages DOM ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function showWelcome() {
    messagesEl.innerHTML = `
        <div class="welcome" id="welcome">
            <div class="welcome-logo">
                <div class="logo-sphere"></div>
                <span class="logo-text">Origine S</span>
            </div>
            <h1 class="welcome-title">Bonjour, <span>Sylvanus</span></h1>
            <p class="welcome-sub">Votre agent IA personnel. Que puis-je faire pour vous ?</p>
            <div class="starters" id="starters">
                <button class="starter-chip" data-prompt="Quelle est la météo à Cotonou en ce moment ?">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9z"/></svg>
                    Météo Cotonou
                </button>
                <button class="starter-chip" data-prompt="Quelles sont les dernières actualités tech ?">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
                    Actualités tech
                </button>
                <button class="starter-chip" data-prompt="Aide-moi à écrire un script Python propre et commenté">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
                    Écrire du code
                </button>
                <button class="starter-chip" data-prompt="Lis mes 5 derniers emails">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
                    Mes emails
                </button>
            </div>
        </div>`;
    document.querySelectorAll('.starter-chip').forEach(btn => {
        btn.addEventListener('click', () => { inputEl.value = btn.dataset.prompt; sendMessage(); });
    });
}

function appendMessage(role, content, msgId) {
    $('welcome')?.remove();
    const msg = document.createElement('div');
    msg.className = `msg ${role}`;
    if (msgId) msg.dataset.msgId = msgId;

    const label = document.createElement('div');
    label.className = 'msg-label';
    label.textContent = role === 'user' ? 'Sylvanus' : 'Origine S';

    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble';

    if (role === 'assistant') {
        bubble.innerHTML = DOMPurify.sanitize(marked.parse(content));
        processCodeBlocks(bubble);
        const cards = buildCards(content);
        if (cards) bubble.appendChild(cards);
    } else {
        bubble.textContent = content;
    }

    msg.appendChild(label);
    msg.appendChild(bubble);
    addActions(msg);
    messagesEl.appendChild(msg);
    return msg;
}

function startAssistantBubble() {
    $('welcome')?.remove();
    const msg = document.createElement('div');
    msg.className = 'msg assistant';
    const label = document.createElement('div');
    label.className = 'msg-label';
    label.textContent = 'Origine S';
    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble';
    bubble.innerHTML = '<span class="cursor"></span>';
    msg.appendChild(label);
    msg.appendChild(bubble);
    messagesEl.appendChild(msg);
    currentAssistantBubble = bubble;
}

function renderStreaming(text) {
    if (!currentAssistantBubble) return;
    currentAssistantBubble.innerHTML = DOMPurify.sanitize(marked.parse(text)) + '<span class="cursor"></span>';
    processCodeBlocks(currentAssistantBubble);
}

function finalizeAssistant(msgId) {
    if (!currentAssistantBubble) return;
    currentAssistantBubble.innerHTML = DOMPurify.sanitize(marked.parse(currentAssistantText));
    processCodeBlocks(currentAssistantBubble);
    const cards = buildCards(currentAssistantText);
    if (cards) currentAssistantBubble.appendChild(cards);
    const msg = currentAssistantBubble.closest('.msg');
    if (msgId && msg) msg.dataset.msgId = msgId;
    addActions(msg);
    currentAssistantBubble = null;
    currentAssistantText = '';
    hideThinking();
}

function processCodeBlocks(container) {
    container.querySelectorAll('pre code').forEach(codeEl => {
        if (codeEl.closest('.code-block')) return;
        const pre = codeEl.parentElement;
        const lang = (codeEl.className.match(/language-(\w+)/) || [])[1] || '';
        hljs.highlightElement(codeEl);
        const wrapper = document.createElement('div');
        wrapper.className = 'code-block';
        const header = document.createElement('div');
        header.className = 'code-header';
        const langSpan = document.createElement('span');
        langSpan.className = 'code-lang';
        langSpan.textContent = lang || 'code';
        const copyBtn = document.createElement('button');
        copyBtn.className = 'code-copy';
        copyBtn.textContent = 'Copier';
        copyBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(codeEl.textContent);
            copyBtn.textContent = 'Copié !';
            setTimeout(() => copyBtn.textContent = 'Copier', 2000);
        });
        header.appendChild(langSpan);
        header.appendChild(copyBtn);
        wrapper.appendChild(header);
        pre.parentNode.insertBefore(wrapper, pre);
        wrapper.appendChild(pre);
    });
}

function addActions(msgEl) {
    if (!msgEl || msgEl.querySelector('.msg-actions')) return;
    const actions = document.createElement('div');
    actions.className = 'msg-actions';
    const copyBtn = document.createElement('button');
    copyBtn.className = 'act-btn';
    copyBtn.textContent = 'Copier';
    copyBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(msgEl.querySelector('.msg-bubble')?.innerText || '');
        copyBtn.textContent = 'Copié !';
        setTimeout(() => copyBtn.textContent = 'Copier', 2000);
    });
    actions.appendChild(copyBtn);
    msgEl.appendChild(actions);
}

function showError(msg) {
    const el = document.createElement('div');
    el.className = 'msg assistant';
    el.innerHTML = `<div class="msg-label">Erreur</div><div class="msg-bubble" style="color:#EF4444;font-size:13px">${msg}</div>`;
    messagesEl.appendChild(el);
    if (autoScroll) scrollToBottom();
}

// ━━ Feature 1 — Card Visualization ━━━━━━━━━━━━━━━━━━━━━━━

const ICONS = {
    mail: '📧', email: '📧', météo: '🌤', weather: '🌤',
    code: '💻', python: '🐍', html: '🌐', script: '💻',
    actualité: '📰', news: '📰', fichier: '📄', file: '📄',
    agenda: '📅', calendrier: '📅', recherche: '🔍',
    erreur: '⚠️', succès: '✅', sécurité: '🔒', web: '🌐',
    ia: '🤖', intelligence: '🤖', données: '📊', api: '⚡'
};

function getIcon(text) {
    const t = text.toLowerCase();
    for (const [k, v] of Object.entries(ICONS)) if (t.includes(k)) return v;
    return '•';
}

function buildCards(text) {
    const bullets = text.split('\n').filter(l => /^[\*\-]\s+.{6,}/.test(l.trim()));
    if (bullets.length < 3 || bullets.length > 8) return null;

    const container = document.createElement('div');
    container.className = 'response-cards';

    bullets.forEach((line, i) => {
        const content = line.replace(/^[\*\-]\s+/, '').trim();
        const sep = content.indexOf(':') > 0 ? ':' : null;
        let title = content, body = '';
        if (sep) {
            const idx = content.indexOf(sep);
            title = content.substring(0, idx).trim();
            body  = content.substring(idx + 1).trim();
        }

        const card = document.createElement('div');
        card.className = 'r-card';
        card.style.animationDelay = `${i * 0.06}s`;

        const icon = document.createElement('span');
        icon.className = 'r-card-icon';
        icon.textContent = getIcon(title + body);

        const titleEl = document.createElement('div');
        titleEl.className = 'r-card-title';
        titleEl.textContent = title;

        card.appendChild(icon);
        card.appendChild(titleEl);

        if (body) {
            const bodyEl = document.createElement('div');
            bodyEl.className = 'r-card-body';
            bodyEl.textContent = body.length > 90 ? body.substring(0, 90) + '…' : body;
            card.appendChild(bodyEl);
        }

        container.appendChild(card);
    });

    return container.children.length >= 3 ? container : null;
}

// ━━ Feature 2 — Export Conversation ━━━━━━━━━━━━━━━━━━━━━━

async function exportConversation() {
    if (!currentConvId) return;
    const [conv, msgs] = await Promise.all([
        fetch(`/api/conversations/${currentConvId}`).then(r => r.json()),
        fetch(`/api/conversations/${currentConvId}/messages`).then(r => r.json())
    ]);
    const date = new Date().toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
    const html = `<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><title>${conv.title} — Origine S</title>
<style>
  body{font-family:system-ui,sans-serif;background:#fff;color:#111;max-width:760px;margin:0 auto;padding:40px 24px;line-height:1.7}
  h1{font-size:22px;font-weight:600;margin-bottom:4px}
  .meta{color:#888;font-size:13px;margin-bottom:40px;border-bottom:1px solid #eee;padding-bottom:20px}
  .msg{margin-bottom:28px}
  .label{font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;margin-bottom:6px}
  .user .label{color:#2563EB}.assistant .label{color:#888}
  .user .bubble{background:#EFF6FF;border-radius:12px;padding:12px 16px;display:inline-block;color:#1e40af}
  .assistant .bubble{font-size:14px}
  pre{background:#f4f4f4;padding:14px;border-radius:8px;overflow-x:auto;font-size:13px}
  code{background:#f0f0f0;padding:2px 5px;border-radius:4px;font-size:12px}
</style></head><body>
<h1>${conv.title}</h1>
<div class="meta">Exporté le ${date} • Origine S</div>
${msgs.map(m => `<div class="msg ${m.role}"><div class="label">${m.role === 'user' ? 'Sylvanus' : 'Origine S'}</div><div class="bubble">${m.role === 'assistant' ? marked.parse(m.content) : m.content}</div></div>`).join('')}
</body></html>`;
    const blob = new Blob([html], { type: 'text/html' });
    const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: `${conv.title.replace(/\s+/g, '-')}.html` });
    a.click();
}

// ━━ Drag & Drop ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function initDragDrop() {
    const main = $('main-content');
    main.addEventListener('dragover', e => { e.preventDefault(); dropzoneOverlay.classList.remove('hidden'); });
    dropzoneOverlay.addEventListener('dragleave', e => { if (!dropzoneOverlay.contains(e.relatedTarget)) dropzoneOverlay.classList.add('hidden'); });
    dropzoneOverlay.addEventListener('drop', async e => {
        e.preventDefault();
        dropzoneOverlay.classList.add('hidden');
        const file = e.dataTransfer.files[0];
        if (!file) return;
        const isText = file.type.startsWith('text') || /\.(py|js|html|css|json|md|txt|csv)$/.test(file.name);
        if (isText) {
            const reader = new FileReader();
            reader.onload = evt => {
                const content = evt.target.result;
                const truncated = content.length > 8000 ? content.substring(0, 8000) + '\n\n[... tronqué ...]' : content;
                inputEl.value = `Analyse ce fichier : "${file.name}"\n\n\`\`\`\n${truncated}\n\`\`\``;
                sendMessage();
            };
            reader.readAsText(file);
        } else {
            inputEl.value = `Sylvanus t'a envoyé un fichier : "${file.name}" (${file.type || 'type inconnu'}, ${(file.size/1024).toFixed(1)} Ko). Dis-lui ce que tu peux faire avec ce type de fichier.`;
            sendMessage();
        }
    });
}

// ━━ Thinking Sphere ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function showThinking() { thinkingBar.classList.remove('hidden'); }
function hideThinking() { thinkingBar.classList.add('hidden'); }

// ━━ Tool indicator ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function showTool(name, input) {
    hideTool();
    const labels = { web_search: 'Recherche web', run_python: 'Python', get_weather: 'Météo', get_datetime: 'Date', read_file: 'Lecture', write_file: 'Écriture', gmail_read: 'Gmail', gmail_send: 'Envoi mail', gmail_search: 'Recherche mail', calendar_read: 'Agenda', calendar_create: 'Événement' };
    const query = input?.query || input?.city || input?.path || '';
    const preview = query ? ` — ${query.substring(0, 30)}` : '';
    const el = document.createElement('div');
    el.className = 'tool-pill';
    el.id = 'tool-indicator';
    el.innerHTML = `<div class="tool-spin"></div><span>${labels[name] || name}${preview}</span>`;
    messagesEl.appendChild(el);
    currentToolEl = el;
    if (autoScroll) scrollToBottom();
}

function hideTool() { currentToolEl?.remove(); currentToolEl = null; }

// ━━ Suggestions ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async function loadSuggestions(convId) {
    try {
        const data = await fetch(`/api/suggestions/${convId}`).then(r => r.json());
        const s = data.suggestions || [];
        if (!s.length) { hideSuggestions(); return; }
        suggestionsBar.innerHTML = s.map(t => `<button class="sugg-chip">${t}</button>`).join('');
        suggestionsBar.querySelectorAll('.sugg-chip').forEach(btn => {
            btn.addEventListener('click', () => { inputEl.value = btn.textContent; hideSuggestions(); sendMessage(); });
        });
        suggestionsBar.classList.remove('hidden');
    } catch (_) {}
}

function hideSuggestions() { suggestionsBar.classList.add('hidden'); suggestionsBar.innerHTML = ''; }

// ━━ Memory ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async function loadMemory() {
    const panel = $('memory-panel');
    panel.classList.toggle('hidden');
    if (panel.classList.contains('hidden')) return;
    const data = await fetch('/api/memory').then(r => r.json());
    const body = $('memory-body');
    const items = data.interactions || [];
    body.innerHTML = !items.length ? 'Aucune interaction mémorisée.' :
        items.slice(-15).map(i => `<div style="margin-bottom:8px">${i.timestamp.slice(0,10)} — ${i.message.slice(0,90)}</div>`).join('');
}

// ━━ Voice ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function toggleVoice() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { alert('Reconnaissance vocale : utilisez Chrome.'); return; }
    if (recognition) { recognition.stop(); recognition = null; $('btn-voice').classList.remove('listening'); return; }
    recognition = new SR();
    recognition.lang = 'fr-FR';
    recognition.onstart = () => $('btn-voice').classList.add('listening');
    recognition.onend = () => { $('btn-voice').classList.remove('listening'); recognition = null; };
    recognition.onresult = e => { inputEl.value = e.results[0][0].transcript; autoResizeInput(); sendMessage(); };
    recognition.onerror = () => { $('btn-voice').classList.remove('listening'); recognition = null; };
    recognition.start();
}

// ━━ Send / Stop ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async function sendMessage() {
    const content = inputEl.value.trim();
    if (!content || isStreaming) return;
    if (!currentConvId) await newConversation();
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    hideSuggestions();
    setStreaming(true);
    appendMessage('user', content);
    scrollToBottom(true);
    inputEl.value = '';
    autoResizeInput();
    showThinking();
    ws.send(JSON.stringify({ action: 'message', content }));
}

function stopGeneration() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ action: 'stop' }));
}

function setStreaming(val) {
    isStreaming = val;
    $('btn-stop').classList.toggle('hidden', !val);
    $('btn-send').classList.toggle('hidden', val);
    if (!val) hideThinking();
}

// ━━ Scroll ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function scrollToBottom(force) {
    if (!force && !autoScroll) return;
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

messagesEl.addEventListener('scroll', () => {
    const atBottom = messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight < 60;
    autoScroll = atBottom;
    $('btn-scroll').classList.toggle('hidden', atBottom);
});

function autoResizeInput() {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 200) + 'px';
}

// ━━ Events ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

$('btn-new').addEventListener('click', newConversation);
$('btn-send').addEventListener('click', sendMessage);
$('btn-stop').addEventListener('click', stopGeneration);
$('btn-voice').addEventListener('click', toggleVoice);
$('btn-memory').addEventListener('click', loadMemory);
$('btn-export').addEventListener('click', exportConversation);
$('btn-close-mem').addEventListener('click', () => $('memory-panel').classList.add('hidden'));
$('btn-delete').addEventListener('click', deleteConversation);
$('btn-rename').addEventListener('click', renameConversation);
$('btn-scroll').addEventListener('click', () => { autoScroll = true; scrollToBottom(true); });
$('btn-menu')?.addEventListener('click', () => document.getElementById('sidebar').classList.toggle('open'));

document.addEventListener('click', e => {
    const sidebar = document.getElementById('sidebar');
    const btn = $('btn-menu');
    if (btn && !sidebar.contains(e.target) && !btn.contains(e.target)) sidebar.classList.remove('open');
});

$('search-input').addEventListener('input', e => renderConversations(e.target.value));
inputEl.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
inputEl.addEventListener('input', () => { autoResizeInput(); hideSuggestions(); });

// ━━ Init ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async function init() {
    initDragDrop();
    await loadConversations();
    if (allConversations.length > 0) openConversation(allConversations[0].id);
}

init();