"use client";
import { useState } from "react";
import { useAgentChat } from "@/lib/useAgentChat";

export default function Home() {
  const { messages, sendMessage } = useAgentChat();
  const [input, setInput] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    sendMessage(text);
    setInput("");
  };

  return (
    <div className="flex flex-col h-screen bg-[color:var(--color-background)]">
      <main className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`max-w-[80%] p-3 rounded-lg whitespace-pre-wrap break-words ${
              m.role === "user"
                ? "bg-blue-600 text-white ml-auto"
                : "bg-gray-200 text-gray-900"
            }`}
          >
            {m.content}
          </div>
        ))}
      </main>
      <form
        onSubmit={handleSubmit}
        className="p-4 flex gap-2 border-t border-gray-300"
      >
        <input
          type="text"
          className="flex-1 border rounded-md px-3 py-2"
          placeholder="Type a message..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button
          type="submit"
          className="bg-blue-600 text-white px-4 py-2 rounded-md"
        >
          Send
        </button>
      </form>
    </div>
  );
}
