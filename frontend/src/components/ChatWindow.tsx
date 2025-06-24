import React, { useState, KeyboardEvent, ChangeEvent, useEffect, useRef } from 'react';
import '../styles/ChatWindow.css';

interface Message {
  id: string;
  text: string;
  sender: 'user' | 'agent';
  timestamp: Date;
}

const ChatWindow: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([
    { id: '1', text: 'Welcome to the OS Agent. How can I assist you today?', sender: 'agent', timestamp: new Date() }
  ]);
  const [inputText, setInputText] = useState<string>('');
  const [isAgentTyping, setIsAgentTyping] = useState<boolean>(false);
  const messageAreaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Scroll to bottom when messages change
    if (messageAreaRef.current) {
      messageAreaRef.current.scrollTop = messageAreaRef.current.scrollHeight;
    }
  }, [messages]);

  const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    setInputText(event.target.value);
  };

  const handleSendMessage = () => {
    if (inputText.trim() === '') return;

    const newUserMessage: Message = {
      id: `user-${Date.now()}`,
      text: inputText,
      sender: 'user',
      timestamp: new Date(),
    };

    setMessages(prevMessages => [...prevMessages, newUserMessage]);
    setInputText('');
    setIsAgentTyping(true); // Start typing indicator

    // Call the backend API
    fetch('http://localhost:8000/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message: newUserMessage.text, session_id: 'mock-session-123' }), // Using a mock session_id for now
    })
    .then(response => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return response.json();
    })
    .then(data => {
      const agentResponse: Message = {
        id: `agent-${Date.now()}`, // Consider using an ID from the backend if available
        text: data.response,
        sender: 'agent',
        timestamp: new Date(data.timestamp), // Use timestamp from backend
      };
      setMessages(prevMessages => [...prevMessages, agentResponse]);
    })
    .catch(error => {
      console.error("Error fetching from backend:", error);
      const errorResponse: Message = {
        id: `error-${Date.now()}`,
        text: `Error connecting to agent: ${error.message}. Please check if the backend is running.`,
        sender: 'agent', // Display error as an agent message
        timestamp: new Date(),
      };
      setMessages(prevMessages => [...prevMessages, errorResponse]);
    })
    .finally(() => {
      setIsAgentTyping(false); // Stop typing indicator regardless of success or failure
    });
  };

  const handleKeyPress = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault(); // Prevent newline in input
      handleSendMessage();
    }
  };

  const initialSuggestions = [
    "What can you do?",
    "Show me the current directory contents.",
    "What's the system load?",
    "Can you open a file for me?",
  ];

  const handleSuggestionClick = (suggestion: string) => {
    setInputText(suggestion);
  };

  return (
    <div className="chat-window-container styled-container">
      <h2>Agent Chat</h2>
      <div className="message-area" ref={messageAreaRef}>
        {messages.map((msg) => (
          <div key={msg.id} className={`message ${msg.sender}-message`}>
            <p className="message-text">{msg.text}</p>
            <span className="message-timestamp">
              {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
        ))}
        {isAgentTyping && (
          <div className="message agent-message typing-indicator">
            <p className="message-text">Agent is typing...</p>
          </div>
        )}
      </div>
      <div className="suggestions-area">
        {initialSuggestions.map((suggestion, index) => (
          <button key={index} className="suggestion-button" onClick={() => handleSuggestionClick(suggestion)}>
            {suggestion}
          </button>
        ))}
      </div>
      <div className="input-area">
        <input
          type="text"
          placeholder="Type your message to the OS Agent..."
          value={inputText}
          onChange={handleInputChange}
          onKeyPress={handleKeyPress}
        />
        <button onClick={handleSendMessage}>Send</button>
      </div>
    </div>
  );
};

export default ChatWindow;
