export class AgentClient {
  constructor({ host = location.hostname, port = 8765, user = 'demo', session = 'main', think = true } = {}) {
    this.host = host;
    this.port = port;
    this.user = user;
    this.session = session;
    this.think = think;
    this.ws = null;
  }

  _buildUri() {
    const t = this.think ? 'true' : 'false';
    return `ws://${this.host}:${this.port}/?user=${encodeURIComponent(this.user)}&session=${encodeURIComponent(this.session)}&think=${t}`;
  }

  connect() {
    if (this.ws) {
      this.ws.close();
    }
    const uri = this._buildUri();
    this.ws = new WebSocket(uri);
    return new Promise((resolve, reject) => {
      this.ws.onopen = () => resolve();
      this.ws.onerror = (e) => reject(e);
    });
  }

  onMessage(cb) {
    if (!this.ws) return;
    this.ws.addEventListener('message', (ev) => cb(ev.data));
  }

  sendCommand(command, args = {}) {
    if (!this.ws) throw new Error('Not connected');
    this.ws.send(JSON.stringify({ command, args }));
  }

  sendPrompt(text) {
    this.sendCommand('team_chat', { prompt: text });
  }

  async uploadFile(file) {
    if (!this.ws) throw new Error('Not connected');
    const header = { command: 'upload_document', args: { file_name: file.name } };
    const headerBytes = new TextEncoder().encode(JSON.stringify(header));
    const lenBuf = new Uint32Array([headerBytes.length]);
    const fileBuf = new Uint8Array(await file.arrayBuffer());
    const payload = new Uint8Array(4 + headerBytes.length + fileBuf.length);
    payload.set(new Uint8Array(lenBuf.buffer), 0);
    payload.set(headerBytes, 4);
    payload.set(fileBuf, 4 + headerBytes.length);
    this.ws.send(payload);
  }

  async uploadAudio(blob, name = 'audio.webm') {
    const file = new File([blob], name, { type: blob.type || 'audio/webm' });
    await this.uploadFile(file);
  }

  async request(command, args = {}) {
    const uri = this._buildUri();
    const ws = new WebSocket(uri);
    return new Promise((resolve, reject) => {
      ws.onopen = () => {
        ws.send(JSON.stringify({ command, args }));
      };
      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if ('result' in data || 'error' in data) {
            ws.close();
            resolve(data);
          }
        } catch {
          /* ignore streaming data */
        }
      };
      ws.onerror = (e) => {
        reject(e);
      };
    });
  }
}
