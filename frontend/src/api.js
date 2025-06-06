export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export async function chat(user, session, prompt) {
  const resp = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user, session, prompt }),
  });
  if (!resp.ok) {
    const msg = await resp.text();
    throw new Error(msg || resp.statusText);
  }
  const data = await resp.json();
  return data.reply;
}

export async function reset(user, session) {
  const resp = await fetch(`${API_BASE}/reset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user, session }),
  });
  if (!resp.ok) {
    const msg = await resp.text();
    throw new Error(msg || resp.statusText);
  }
  const data = await resp.json();
  return data.removed;
}
