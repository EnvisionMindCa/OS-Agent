import { useState } from 'react'
import './App.css'
import { chat as chatApi, reset as resetApi } from './api'

function App() {
  const [user, setUser] = useState('default')
  const [session, setSession] = useState('default')
  const [prompt, setPrompt] = useState('')
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const sendPrompt = async () => {
    if (!prompt.trim()) return
    setLoading(true)
    setError(null)
    try {
      const reply = await chatApi(user, session, prompt)
      setMessages([...messages, { role: 'user', content: prompt }, { role: 'assistant', content: reply }])
      setPrompt('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleReset = async () => {
    setLoading(true)
    setError(null)
    try {
      await resetApi(user, session)
      setMessages([])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="container">
      <h1>LLM Chat</h1>
      <div className="controls">
        <label>User <input value={user} onChange={e => setUser(e.target.value)} /></label>
        <label>Session <input value={session} onChange={e => setSession(e.target.value)} /></label>
        <button onClick={handleReset} disabled={loading}>Reset</button>
      </div>
      <div className="chat-box">
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>{m.role}: {m.content}</div>
        ))}
      </div>
      {error && <div className="error">{error}</div>}
      <div className="input-area">
        <textarea value={prompt} onChange={e => setPrompt(e.target.value)} rows="3" />
        <button onClick={sendPrompt} disabled={loading}>Send</button>
      </div>
    </div>
  )
}

export default App
