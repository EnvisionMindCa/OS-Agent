import { useEffect, useState } from 'react'
import MessageList from './MessageList'
import InputBar from './InputBar'
import SessionList from './SessionList'
import UsernameForm from './UsernameForm'
import '../styles/chat.css'
import { fetchStream, fetchSessions } from '../api'

function ChatWindow() {
  const [messages, setMessages] = useState([])
  const [sessionName] = useState(() => crypto.randomUUID())
  const [sessions, setSessions] = useState([])
  const [username, setUsername] = useState(() =>
    localStorage.getItem('username') || ''
  )

  useEffect(() => {
    if (username) {
      fetchSessions(username).then(setSessions)
    }
  }, [username])

  const refreshSessions = () => {
    if (username) {
      fetchSessions(username).then(setSessions)
    }
  }

  const sendMessage = async (text) => {
    const userMsg = { role: 'user', content: text }
    setMessages((prev) => [...prev, userMsg, { role: 'assistant', content: '' }])
    const index = messages.length + 1
    await fetchStream(username, sessionName, text, (chunk) => {
      setMessages((prev) => {
        const copy = [...prev]
        copy[index] = { ...copy[index], content: copy[index].content + chunk }
        return copy
      })
    })
    refreshSessions()
  }

  const handleUsernameSet = (name) => {
    localStorage.setItem('username', name)
    setUsername(name)
  }

  return (
    <div className="chat-container">
      {!username ? (
        <UsernameForm onSet={handleUsernameSet} />
      ) : (
        <>
          <SessionList sessions={sessions} current={sessionName} />
          <MessageList messages={messages} />
          <InputBar onSend={sendMessage} />
        </>
      )}
    </div>
  )
}

export default ChatWindow
