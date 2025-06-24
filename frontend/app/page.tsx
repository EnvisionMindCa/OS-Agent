"use client";
import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { useAgentChat } from "@/lib/useAgentChat";

export default function Home() {
  const searchParams = useSearchParams();
  const initialSession = searchParams.get("session") || "main";
  const { messages, sendMessage, uploadFile } = useAgentChat({
    session: initialSession,
  });
  const [input, setInput] = useState("");
  const [sessionInput, setSessionInput] = useState(initialSession);
  const [file, setFile] = useState<File | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    sendMessage(text);
    setInput("");
  };

  const handleSessionUpdate = () => {
    const s = sessionInput.trim();
    if (!s) return;
    const url = new URL(window.location.href);
    url.searchParams.set("session", s);
    window.location.href = url.toString();
  };

  const handleUpload = (e: React.FormEvent) => {
    e.preventDefault();
    if (file) {
      uploadFile(file);
      setFile(null);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-slate-900 to-gray-700 text-white">
      <header className="p-4 flex gap-2 backdrop-blur-md bg-white/10 border-b border-white/30">
        <input
          type="text"
          className="flex-1 rounded-md bg-white/20 backdrop-blur px-3 py-2 placeholder-white/70"
          placeholder="Session ID"
          value={sessionInput}
          onChange={(e) => setSessionInput(e.target.value)}
        />
        <button
          type="button"
          onClick={handleSessionUpdate}
          className="px-4 py-2 rounded-md bg-blue-600/80 text-white"
        >
          Set
        </button>
      </header>
      <main className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`max-w-[80%] p-3 rounded-lg whitespace-pre-wrap break-words backdrop-blur-md border ${
              m.role === "user"
                ? "bg-blue-600/60 text-white ml-auto border-blue-300/30"
                : "bg-white/20 text-white border-white/30"
            }`}
          >
            {m.file ? (
              <a href={m.file.url} download={m.file.name} className="underline">
                {m.file.name}
              </a>
            ) : (
              m.content
            )}
          </div>
        ))}
      </main>
      <form
        onSubmit={handleSubmit}
        className="p-4 flex flex-col gap-2 backdrop-blur-md bg-white/10 border-t border-white/30"
      >
        <input
          type="text"
          className="flex-1 border rounded-md px-3 py-2 bg-white/20 backdrop-blur placeholder-white/70"
          placeholder="Type a message..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <div className="flex gap-2 mt-2">
          <input
            type="file"
            className="flex-1 text-white"
            onChange={(e) => setFile(e.target.files ? e.target.files[0] : null)}
          />
          <button
            type="button"
            onClick={handleUpload}
            className="px-4 py-2 rounded-md bg-green-600/80"
          >
            Upload
          </button>
          <button
            type="submit"
            className="px-4 py-2 rounded-md bg-blue-600/80"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
}
