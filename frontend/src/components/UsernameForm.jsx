import { useState } from 'react'
import PropTypes from 'prop-types'
import '../styles/chat.css'

function UsernameForm({ onSet }) {
  const [name, setName] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return
    onSet(trimmed)
  }

  return (
    <form className="username-form" onSubmit={handleSubmit}>
      <input
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Enter your name..."
      />
      <button type="submit">Start Chatting</button>
    </form>
  )
}

UsernameForm.propTypes = {
  onSet: PropTypes.func.isRequired,
}

export default UsernameForm
