import { useEffect, useRef, useState, useCallback } from "react";
import { Base64 } from "js-base64";

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
  const { user = "demo", session: initSession = "main", think = true } = options;
  const [session, setSession] = useState(initSession);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const shouldReconnect = useRef(true);
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
        setTimeout(connect, 1000);
      }
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
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        connect();
      }
      const data = await blob.arrayBuffer();
      // Audio files are transcribed server-side and the resulting
      // ``<name>_transcription.txt`` file is saved in the VM.
      wsRef.current?.send(data);
    },
    [connect]
  );

  const changeSession = useCallback((s: string) => {
    setSession(s);
    setMessages([]);
  }, []);

  return { messages, sendMessage, uploadFile, setSession: changeSession, session };
}
