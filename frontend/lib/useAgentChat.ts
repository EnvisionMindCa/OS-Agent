import { useEffect, useRef, useState, useCallback } from "react";
import { Base64 } from "js-base64";

const DEFAULT_WS_URL = process.env.NEXT_PUBLIC_AGENT_WS_URL || "ws://localhost:8765";

function buildWSUrl(user: string, session: string, think: boolean): string {
  const url = new URL(DEFAULT_WS_URL);
  url.searchParams.set("user", user);
  url.searchParams.set("session", session);
  url.searchParams.set("think", think ? "true" : "false");
  return url.toString();
}

function sendJSON(ws: WebSocket | null, payload: unknown) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(payload));
  }
}

export interface ChatFile {
  name: string;
  url: string;
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  file?: ChatFile;
}

export interface UseAgentChatOptions {
  user?: string;
  session?: string;
  think?: boolean;
}

export function useAgentChat(options: UseAgentChatOptions = {}) {
  const { user = "demo", session: initSession = "main", think = false } = options;
  const [session, setSession] = useState(initSession);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const queueRef = useRef<Array<{ type: "json" | "binary"; data: any }>>([]);
  const shouldReconnect = useRef(true);
  const reconnectAttempts = useRef(0);
  const idRef = useRef(0);

  const flushQueue = useCallback(() => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    while (queueRef.current.length > 0) {
      const item = queueRef.current.shift()!;
      if (item.type === "json") {
        sendJSON(ws, item.data);
      } else {
        ws.send(item.data);
      }
    }
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current) {
      if (
        wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING
      ) {
        return;
      }
      wsRef.current.close();
    }

    const ws = new WebSocket(buildWSUrl(user, session, think));

    ws.onopen = () => {
      reconnectAttempts.current = 0;
      flushQueue();
    };

    ws.onmessage = (e) => {
      const raw = e.data as string;
      try {
        const data = JSON.parse(raw);
        if (data.returned_file && data.data) {
          const bytes = Base64.toUint8Array(String(data.data));
          const url = URL.createObjectURL(new Blob([bytes]));
          setMessages((prev) => [
            ...prev,
            {
              id: idRef.current++,
              role: "assistant",
              content: data.returned_file,
              file: { name: data.returned_file, url },
            },
          ]);
          return;
        }
        if (typeof data.result === "string") {
          setMessages((prev) => [
            ...prev,
            {
              id: idRef.current++,
              role: "assistant",
              content: data.result,
            },
          ]);
          return;
        }
      } catch {
        /* not JSON */
      }
      const part = raw;
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.role === "assistant" && !last.file) {
          const prefix = last.content ? "\n\n" : "";
          const updated = {
            ...last,
            content: last.content + prefix + part,
          };
          return [...prev.slice(0, -1), updated];
        }
        return [
          ...prev,
          { id: idRef.current++, role: "assistant", content: part },
        ];
      });
    };

    ws.onclose = () => {
      if (shouldReconnect.current) {
        reconnectAttempts.current += 1;
        const delay = Math.min(1000 * 2 ** reconnectAttempts.current, 30000);
        setTimeout(connect, delay);
      }
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  }, [user, session, think]);

  useEffect(() => {
    shouldReconnect.current = true;
    connect();
    return () => {
      shouldReconnect.current = false;
      wsRef.current?.close();
    };
  }, [connect]);

  const sendCommand = useCallback(
    (command: string, args: Record<string, unknown> = {}) => {
      const payload = { type: "json" as const, data: { command, args } };
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        sendJSON(wsRef.current, payload.data);
      } else {
        queueRef.current.push(payload);
        connect();
      }
    },
    [connect]
  );

  const sendMessage = useCallback(
    (text: string) => {
      sendCommand("team_chat", { prompt: text });
      setMessages((prev) => [
        ...prev,
        { id: idRef.current++, role: "user", content: text },
        { id: idRef.current++, role: "assistant", content: "" },
      ]);
    },
    [sendCommand]
  );

  const uploadFile = useCallback(
    async (file: File) => {
      const header = JSON.stringify({
        command: "upload_document",
        args: { file_name: file.name },
      });
      const headerBytes = new TextEncoder().encode(header);
      const lenBuf = new ArrayBuffer(4);
      new DataView(lenBuf).setUint32(0, headerBytes.length, false);
      const blob = new Blob([lenBuf, headerBytes, file]);
      const data = await blob.arrayBuffer();
      const payload = { type: "binary" as const, data };
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(data);
      } else {
        queueRef.current.push(payload);
        connect();
      }
    },
    [connect]
  );

  const changeSession = useCallback((s: string) => {
    setSession(s);
    setMessages([]);
  }, []);

  return { messages, sendMessage, uploadFile, setSession: changeSession, session };
}
