'use client';

import { useState, useRef, useEffect } from 'react';
import { streamChat, ChatRequest } from '../utils/api';
import MessageList from './MessageList';
import MessageInput from './MessageInput';
import { Message } from './MessageItem';

export default function ChatApp() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  const scrollToEnd = () => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToEnd();
  }, [messages]);

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
      }
    } catch (err) {
      console.error(err);
      setMessages((prev) => {
        const msgs = [...prev];
        msgs[msgs.length - 1] = { role: 'assistant', content: 'Error retrieving response' };
        return msgs;
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center h-screen bg-gradient-to-br from-white to-gray-100 text-gray-900 p-4">
      <div className="w-full max-w-3xl flex flex-col flex-1 glass-panel rounded-lg overflow-hidden">
        <MessageList ref={listRef} messages={messages} />
        <MessageInput value={input} onChange={setInput} onSend={sendMessage} disabled={loading} />
      </div>
    </div>
  );
}
