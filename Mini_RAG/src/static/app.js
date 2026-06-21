/* ===========================================================
   Mini RAG Chat — Application Logic
   ===========================================================
   PROJECT_ID CONFIG:
   ──────────────────
   Change the constant below to target a different project.
   This is the only place you need to update.
   =========================================================== */
const PROJECT_ID = 1; // ← Change this to switch projects

// ── API Base ──
const API = `/api/v1`;

// ── DOM References ──
const chatArea       = document.getElementById('chatArea');
const welcomeScreen  = document.getElementById('welcomeScreen');
const messageInput   = document.getElementById('messageInput');
const sendBtn        = document.getElementById('sendBtn');
const fileInput      = document.getElementById('fileInput');
const attachBtn      = document.getElementById('attachBtn');
const fileChips      = document.getElementById('fileChips');
const typingIndicator= document.getElementById('typingIndicator');
const toastContainer = document.getElementById('toastContainer');

// ── State ──
let isProcessing = false;
let chatHistory = [];

// ─────────────────────────────────────────────
//  MESSAGES
// ─────────────────────────────────────────────

function getTimeString() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function addMessage(text, role, fullPrompt) {
  // Hide welcome screen on first message
  if (welcomeScreen) {
    welcomeScreen.style.display = 'none';
  }

  // Add standard user/bot messages to conversation history (ignoring errors)
  if ((role === 'user' || role === 'bot') && text && !text.startsWith('⚠')) {
    chatHistory.push({ role: role, text: text });
  }

  const msg = document.createElement('div');
  msg.classList.add('message', role);

  const avatarEmoji = role === 'user' ? '👤' : '🤖';

  // Build optional debug prompt block
  let debugBlock = '';
  if (fullPrompt && role === 'bot') {
    debugBlock = `
      <details class="debug-prompt">
        <summary>🔍 Show Full Prompt</summary>
        <pre class="debug-prompt-content">${escapeHtml(typeof fullPrompt === 'string' ? fullPrompt : JSON.stringify(fullPrompt, null, 2))}</pre>
      </details>
    `;
  }

  // Parse message body to HTML: Use marked.parse for bot responses containing markdown
  let messageBodyHtml = '';
  if (role === 'bot') {
    if (typeof marked !== 'undefined') {
      messageBodyHtml = marked.parse(text);
    } else {
      console.warn("Marked library is not loaded. Falling back to plain text with linebreaks.");
      messageBodyHtml = escapeHtml(text).replace(/\n/g, '<br>');
    }
  } else {
    messageBodyHtml = escapeHtml(text).replace(/\n/g, '<br>');
  }

  msg.innerHTML = `
    <div class="message-avatar">${avatarEmoji}</div>
    <div class="message-content">
      <div class="message-bubble">${messageBodyHtml}</div>
      ${debugBlock}
      <span class="message-time">${getTimeString()}</span>
    </div>
  `;

  // Insert before typing indicator
  chatArea.insertBefore(msg, typingIndicator);
  scrollToBottom();
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function scrollToBottom() {
  // Use a slight timeout to let the browser complete Markdown layout calculations
  setTimeout(() => {
    chatArea.scrollTop = chatArea.scrollHeight;
  }, 50);
}

// ─────────────────────────────────────────────
//  TYPING INDICATOR
// ─────────────────────────────────────────────

function showTyping() {
  typingIndicator.classList.add('visible');
  scrollToBottom();
}

function hideTyping() {
  typingIndicator.classList.remove('visible');
}

// ─────────────────────────────────────────────
//  SEND MESSAGE (RAG Answer)
// ─────────────────────────────────────────────

async function sendMessage() {
  const text = messageInput.value.trim();
  if (!text || isProcessing) return;

  // Capture the conversation history prior to the current user message
  const historyToSend = [...chatHistory];

  addMessage(text, 'user');
  messageInput.value = '';
  autoResizeTextarea();

  isProcessing = true;
  sendBtn.disabled = true;
  showTyping();

  try {
    const res = await fetch(`${API}/nlp/index/answer/${PROJECT_ID}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, limit: 5, chat_history: historyToSend }),
    });

    const data = await res.json();

    hideTyping();

    if (res.ok && data.answer) {
      addMessage(data.answer, 'bot', data.full_prompt);
    } else {
      const errMsg = data.signal || 'Something went wrong. Please try again.';
      addMessage(`⚠ ${errMsg}`, 'bot');
    }
  } catch (err) {
    hideTyping();
    addMessage('⚠ Unable to reach the server. Please check the connection.', 'bot');
    console.error('RAG answer error:', err);
  } finally {
    isProcessing = false;
    sendBtn.disabled = false;
    messageInput.focus();
  }
}

// ─────────────────────────────────────────────
//  FILE UPLOAD PIPELINE
// ─────────────────────────────────────────────

attachBtn.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  // Create chip UI
  const chip = createFileChip(file.name);
  fileChips.appendChild(chip);
  fileInput.value = ''; // reset so same file can be re-selected

  try {
    // Step 1: Upload
    updateChipStatus(chip, 'uploading', 'Uploading…');
    const fileId = await uploadFile(file);

    // Step 2: Process
    updateChipStatus(chip, 'processing', 'Processing…');
    await processFile(fileId);

    // Step 3: Index
    updateChipStatus(chip, 'indexing', 'Indexing…');
    await indexProject();

    // Done
    updateChipStatus(chip, 'ready', 'Ready ✓');
    showToast('success', `${file.name} is ready — you can now ask questions about it!`);

    // Auto-remove chip after 4s
    setTimeout(() => {
      chip.style.animation = 'slideOutRight 0.3s forwards';
      setTimeout(() => chip.remove(), 300);
    }, 4000);

  } catch (err) {
    updateChipStatus(chip, 'error', 'Failed');
    showToast('error', `Failed to process ${file.name}: ${err.message}`);
    console.error('Upload pipeline error:', err);
  }
});

async function uploadFile(file) {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API}/data/upload/${PROJECT_ID}`, {
    method: 'POST',
    body: formData,
  });

  const data = await res.json();
  if (!res.ok) throw new Error(data.signal || 'Upload failed');
  return data.file_id;
}

async function processFile(fileId) {
  const res = await fetch(`${API}/data/process/${PROJECT_ID}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      file_id: fileId,
      chunk_size: 1200,      // Upgraded from 100 to 1200 for full paragraphs/lists
      overlap_size: 200,     // Upgraded from 20 to 200 to preserve boundary context
      do_reset: 0,
    }),
  });

  const data = await res.json();
  if (!res.ok) throw new Error(data.signal || 'Processing failed');
  return data;
}

async function indexProject() {
  const res = await fetch(`${API}/nlp/index/push/${PROJECT_ID}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ do_reset: 0 }),
  });

  const data = await res.json();
  if (!res.ok) throw new Error(data.signal || 'Indexing failed');
  return data;
}

// ─────────────────────────────────────────────
//  FILE CHIP UI
// ─────────────────────────────────────────────

function createFileChip(fileName) {
  const chip = document.createElement('div');
  chip.classList.add('file-chip');
  chip.innerHTML = `
    <span class="file-icon">📄</span>
    <span class="file-name">${escapeHtml(fileName)}</span>
    <span class="file-status uploading"><span class="spinner-inline"></span>Queued</span>
    <button class="remove-file" title="Remove">✕</button>
  `;

  chip.querySelector('.remove-file').addEventListener('click', () => {
    chip.style.animation = 'slideOutRight 0.3s forwards';
    setTimeout(() => chip.remove(), 300);
  });

  return chip;
}

function updateChipStatus(chip, statusClass, label) {
  const statusEl = chip.querySelector('.file-status');
  statusEl.className = 'file-status ' + statusClass;

  const needsSpinner = ['uploading', 'processing', 'indexing'].includes(statusClass);
  statusEl.innerHTML = needsSpinner
    ? `<span class="spinner-inline"></span>${label}`
    : label;
}

// ─────────────────────────────────────────────
//  TOASTS
// ─────────────────────────────────────────────

function showToast(type, message) {
  const icons = { success: '✅', error: '❌', info: 'ℹ️' };

  const toast = document.createElement('div');
  toast.classList.add('toast', type);
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || 'ℹ️'}</span>
    <span>${escapeHtml(message)}</span>
  `;

  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('fade-out');
    setTimeout(() => toast.remove(), 300);
  }, 5000);
}

// ─────────────────────────────────────────────
//  INPUT HANDLING
// ─────────────────────────────────────────────

// Auto-resize textarea
function autoResizeTextarea() {
  messageInput.style.height = 'auto';
  messageInput.style.height = Math.min(messageInput.scrollHeight, 150) + 'px';
}

messageInput.addEventListener('input', autoResizeTextarea);

// Enter to send, Shift+Enter for newline
messageInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

sendBtn.addEventListener('click', sendMessage);

// ─────────────────────────────────────────────
//  HINT CHIPS (welcome screen)
// ─────────────────────────────────────────────

document.querySelectorAll('.hint-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    messageInput.value = chip.textContent;
    messageInput.focus();
    autoResizeTextarea();
  });
});

// ─────────────────────────────────────────────
//  INIT
// ─────────────────────────────────────────────

messageInput.focus();
