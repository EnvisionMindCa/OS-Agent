import React, { forwardRef } from 'react';
import MessageItem, { Message } from './MessageItem';

interface MessageListProps {
  messages: Message[];
}

const MessageList = forwardRef<HTMLDivElement, MessageListProps>(({ messages }, ref) => {
  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4" ref={ref}>
      {messages.map((msg, idx) => (
        <MessageItem key={idx} message={msg} />
      ))}
    </div>
  );
});

MessageList.displayName = 'MessageList';

export default MessageList;
