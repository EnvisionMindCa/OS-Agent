'use client';

import { useState, useRef } from 'react';
import { streamChat, ChatRequest } from '../utils/api';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export default function ChatApp() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const scrollToEnd = () => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const prompt = input;
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: prompt }, { role: 'assistant', content: '' }]);
    setLoading(true);
    try {
      const req: ChatRequest = { user: 'demo', session: 'default', prompt };
      for await (const chunk of streamChat(req)) {
        setMessages((prev) => {
          const msgs = [...prev];
          msgs[msgs.length - 1] = {
            role: 'assistant',
            content: msgs[msgs.length - 1].content + chunk,
          };
          return msgs;
        });
        scrollToEnd();
      }
    } catch (err) {
      console.error(err);
      setMessages((prev) => {
        const msgs = [...prev];
        msgs[msgs.length - 1] = {
          role: 'assistant',
          content: 'Error retrieving response',
        };
        return msgs;
      });
    } finally {
      setLoading(false);
      scrollToEnd();
    }
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void sendMessage();
  };

  return (
    <div className="flex flex-col max-w-2xl mx-auto h-screen p-4">
      <div className="flex-1 overflow-y-auto space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx} className={msg.role === 'user' ? 'text-right' : 'text-left'}>
            <span className="px-3 py-2 inline-block rounded bg-gray-200 dark:bg-gray-700">
              {msg.content}
            </span>
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <form onSubmit={onSubmit} className="mt-4 flex gap-2">
        <input
          type="text"
          className="flex-1 border rounded px-3 py-2 text-black"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your message..."
        />
        <button
          type="submit"
          className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
          disabled={loading}
        >
          Send
        </button>
      </form>
    </div>
  );
}
