import { useEffect, useRef, useState, useCallback } from "react";

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
}

export interface UseAgentChatOptions {
  user?: string;
  session?: string;
  think?: boolean;
}

export function useAgentChat(options: UseAgentChatOptions = {}) {
  const { user = "demo", session = "main", think = true } = options;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const idRef = useRef(0);

  const connect = useCallback(() => {
    if (wsRef.current) wsRef.current.close();

    const url = new URL(
      process.env.NEXT_PUBLIC_AGENT_WS_URL || "ws://localhost:8765"
    );
    url.searchParams.set("user", user);
    url.searchParams.set("session", session);
    url.searchParams.set("think", think ? "true" : "false");

    const ws = new WebSocket(url.toString());

    ws.onmessage = (e) => {
      const part = e.data as string;
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.role === "assistant") {
          // append streamed tokens
          const updated = { ...last, content: last.content + part };
          return [...prev.slice(0, -1), updated];
        }
        return [
          ...prev,
          { id: idRef.current++, role: "assistant", content: part },
        ];
      });
    };

    wsRef.current = ws;
  }, [user, session, think]);

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);

  const sendMessage = useCallback(
    (text: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        connect();
      }
      wsRef.current?.send(
        JSON.stringify({ command: "team_chat", args: { prompt: text } })
      );
      setMessages((prev) => [
        ...prev,
        { id: idRef.current++, role: "user", content: text },
        { id: idRef.current++, role: "assistant", content: "" },
      ]);
    },
    [connect]
  );

  return { messages, sendMessage };
}
