import { useState } from 'react'
import MessageList from './MessageList'
import InputBar from './InputBar'
import '../styles/chat.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/chat/stream'

async function fetchStream(prompt, onChunk) {
  const res = await fetch(API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user: 'demo', session: 'default', prompt }),
  })
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    onChunk(decoder.decode(value))
  }
}

function ChatWindow() {
  const [messages, setMessages] = useState([])

  const sendMessage = async (text) => {
    const userMsg = { role: 'user', content: text }
    setMessages((prev) => [...prev, userMsg, { role: 'assistant', content: '' }])
    const index = messages.length + 1
    await fetchStream(text, (chunk) => {
      setMessages((prev) => {
        const copy = [...prev]
        copy[index] = { ...copy[index], content: copy[index].content + chunk }
        return copy
      })
    })
  }

  return (
    <div className="chat-container">
      <MessageList messages={messages} />
      <InputBar onSend={sendMessage} />
    </div>
  )
}

export default ChatWindow
