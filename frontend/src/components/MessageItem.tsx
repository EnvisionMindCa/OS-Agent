import React from 'react';

export interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface MessageItemProps {
  message: Message;
}

export default function MessageItem({ message }: MessageItemProps) {
  const alignment = message.role === 'user' ? 'items-end' : 'items-start';
  return (
    <div className={`flex flex-col ${alignment} animate-fadeIn`}>
      <div className="w-full max-w-xl p-3 my-2 glass-panel rounded-lg shadow-md">
        <p className="whitespace-pre-wrap">{message.content}</p>
      </div>
    </div>
  );
}
