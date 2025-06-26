import { AgentClient } from './api.js';

const state = {
  client: null,
  messages: [],
  recording: false,
  mediaRecorder: null,
  chunks: [],
};

function el(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => {
    if (k === 'class') e.className = v;
    else if (k === 'dataset') Object.entries(v).forEach(([dk, dv]) => e.dataset[dk] = dv);
    else if (k in e) e[k] = v;
    else e.setAttribute(k, v);
  });
  children.forEach(c => e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c));
  return e;
}

function render() {
  const main = document.querySelector('main');
  main.innerHTML = '';
  state.messages.forEach(m => {
    const msgEl = el('div', { class: `message ${m.role}` });
    if (m.file) {
      const link = el('a', { href: m.file.url, download: m.file.name, target: '_blank' }, m.file.name);
      msgEl.appendChild(link);
    } else {
      msgEl.textContent = m.content;
    }
    main.appendChild(msgEl);
  });
  main.scrollTop = main.scrollHeight;
}

function addMessage(role, content) {
  state.messages.push({ role, content });
  render();
}

function addFileMessage(name, url) {
  state.messages.push({ role: 'assistant', file: { name, url } });
  render();
}

function setupUI() {
  const app = document.getElementById('app');
  const userInput = el('input', { id: 'user', value: 'demo', placeholder: 'Username' });
  const sessionInput = el('input', { id: 'session', value: 'main', placeholder: 'Session' });
  const thinkCheck = el('input', { id: 'think', type: 'checkbox', checked: true });
  const connectBtn = el('button', { id: 'connect' }, 'Connect');
  const sessionSelect = el('select', { id: 'sessions' });
  const header = el('header', {},
    userInput,
    sessionInput,
    el('label', {}, thinkCheck, ' Think'),
    connectBtn,
    sessionSelect
  );

  const main = el('main');

  const textInput = el('textarea', { id: 'text', placeholder: 'Type a message...' });
  const fileInput = el('input', { type: 'file', id: 'file' });
  const fileBtn = el('button', { id: 'sendFile' }, 'Upload');
  const recordBtn = el('button', { id: 'record' }, 'Record');
  const sendBtn = el('button', { id: 'send' }, 'Send');
  const controls = el('div', { class: 'controls' }, fileInput, fileBtn, recordBtn, sendBtn);

  const form = el('form', {}, textInput, controls);

  app.append(header, main, form);

  connectBtn.addEventListener('click', async () => {
    state.client = new AgentClient({
      user: userInput.value.trim() || 'demo',
      session: sessionInput.value.trim() || 'main',
      think: thinkCheck.checked,
    });
    await state.client.connect();
    state.client.onMessage(handleMessage);
    state.messages = [];
    render();
    loadSessions();
  });

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = textInput.value.trim();
    if (!text) return;
    addMessage('user', text);
    state.client.sendPrompt(text);
    textInput.value = '';
  });

  fileBtn.addEventListener('click', async () => {
    const file = fileInput.files[0];
    if (!file) return;
    addMessage('user', `[file] ${file.name}`);
    await state.client.uploadFile(file);
    fileInput.value = '';
  });

  recordBtn.addEventListener('click', () => {
    if (state.recording) {
      state.mediaRecorder.stop();
      recordBtn.textContent = 'Record';
      state.recording = false;
    } else {
      navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
        state.mediaRecorder = new MediaRecorder(stream);
        state.chunks = [];
        state.mediaRecorder.ondataavailable = e => state.chunks.push(e.data);
        state.mediaRecorder.onstop = async () => {
          const blob = new Blob(state.chunks, { type: 'audio/webm' });
          addMessage('user', '[audio]');
          await state.client.uploadAudio(blob);
        };
        state.mediaRecorder.start();
        recordBtn.textContent = 'Stop';
        state.recording = true;
      });
    }
  });

  sendBtn.addEventListener('click', () => {
    form.dispatchEvent(new Event('submit'));
  });
}

function handleMessage(raw) {
  try {
    const data = JSON.parse(raw);
    if (data.error) {
      addMessage('assistant', 'Error: ' + data.error);
    } else if (data.result) {
      const text = String(data.result);
      if (text.startsWith('returns/')) {
        const name = text.split('/').pop();
        addFileMessage(name, `files/${name}`);
      } else {
        addMessage('assistant', text);
      }
    }
  } catch {
    const last = state.messages[state.messages.length - 1];
    if (last && last.role === 'assistant' && !last.file) {
      last.content += raw;
    } else {
      state.messages.push({ role: 'assistant', content: raw });
    }
    render();
  }
}

async function loadSessions() {
  if (!state.client) return;
  const resp = await state.client.request('list_sessions');
  const select = document.getElementById('sessions');
  select.innerHTML = '';
  resp.result.forEach(s => {
    const opt = document.createElement('option');
    opt.value = s;
    opt.textContent = s;
    select.appendChild(opt);
  });
  select.value = state.client.session;
  select.onchange = () => {
    document.getElementById('session').value = select.value;
    document.getElementById('connect').click();
  };
}

setupUI();
