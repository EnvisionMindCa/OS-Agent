export function getWsUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_AGENT_WS_URL;
  if (envUrl) return envUrl;
  if (typeof window === 'undefined') return 'ws://localhost:8765';
  const { protocol, hostname } = window.location;
  const scheme = protocol === 'https:' ? 'wss' : 'ws';
  return `${scheme}://${hostname}:8765`;
}
