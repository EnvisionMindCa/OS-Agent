const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export async function fetchStream(user, session, prompt, onChunk) {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user, session, prompt }),
  });
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    onChunk(decoder.decode(value));
  }
}

export async function fetchSessions(user) {
  const res = await fetch(`${API_BASE}/sessions/${encodeURIComponent(user)}`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.sessions ?? [];
}
