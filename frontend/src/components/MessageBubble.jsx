import PropTypes from 'prop-types'
import '../styles/chat.css'

function MessageBubble({ role, content }) {
  return <div className={`message ${role}`}>{content}</div>
}

MessageBubble.propTypes = {
  role: PropTypes.string.isRequired,
  content: PropTypes.string.isRequired,
}

export default MessageBubble
