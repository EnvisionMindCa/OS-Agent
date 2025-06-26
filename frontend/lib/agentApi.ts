export interface AgentApiOptions {
  user?: string;
  session?: string;
  think?: boolean;
  timeoutMs?: number;
}

export async function sendAgentCommand<T = unknown>(
  command: string,
  args: Record<string, unknown> = {},
  options: AgentApiOptions = {}
): Promise<T> {
  const {
    user = "demo",
    session = "main",
    think = true,
    timeoutMs = 10000,
  } = options;
  const url = new URL(
    process.env.NEXT_PUBLIC_AGENT_WS_URL || "ws://localhost:8765"
  );
  url.searchParams.set("user", user);
  url.searchParams.set("session", session);
  url.searchParams.set("think", think ? "true" : "false");

  return new Promise<T>((resolve, reject) => {
    const ws = new WebSocket(url.toString());
    const timer = setTimeout(() => {
      ws.close();
      reject(new Error("timeout"));
    }, timeoutMs);

    ws.onerror = (err) => {
      clearTimeout(timer);
      ws.close();
      reject(err instanceof Event ? new Error("WebSocket error") : (err as any));
    };

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data as string);
        if (data.result !== undefined) {
          clearTimeout(timer);
          ws.close();
          resolve(data.result as T);
        }
      } catch {
        // ignore non JSON
      }
    };

    ws.onopen = () => {
      ws.send(JSON.stringify({ command, args }));
    };
  });
}
