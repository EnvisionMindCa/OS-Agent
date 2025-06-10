import PropTypes from 'prop-types'
import '../styles/chat.css'

function SessionList({ sessions, current }) {
  return (
    <div className="session-list">
      {sessions.map((name) => (
        <span
          key={name}
          className={`session-item ${name === current ? 'active' : ''}`}
        >
          {name}
        </span>
      ))}
    </div>
  )
}

SessionList.propTypes = {
  sessions: PropTypes.arrayOf(PropTypes.string).isRequired,
  current: PropTypes.string.isRequired,
}

export default SessionList
