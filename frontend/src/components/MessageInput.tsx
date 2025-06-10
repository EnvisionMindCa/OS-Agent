import React from 'react';
import GlassButton from './ui/GlassButton';

interface MessageInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  disabled?: boolean;
}

export default function MessageInput({ value, onChange, onSend, disabled }: MessageInputProps) {
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSend();
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 p-2">
      <input
        type="text"
        className="flex-1 bg-white/20 backdrop-blur-md border border-white/30 text-white px-3 py-2 rounded-md focus:outline-none"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Type your message..."
      />
      <GlassButton type="submit" disabled={disabled}>
        Send
      </GlassButton>
    </form>
  );
}
