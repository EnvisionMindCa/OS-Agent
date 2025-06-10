import PropTypes from 'prop-types'
import MessageBubble from './MessageBubble'

function MessageList({ messages }) {
  return (
    <div className="message-list">
      {messages.map((m, i) => (
        <MessageBubble key={i} role={m.role} content={m.content} />
      ))}
    </div>
  )
}

MessageList.propTypes = {
  messages: PropTypes.arrayOf(
    PropTypes.shape({
      role: PropTypes.string.isRequired,
      content: PropTypes.string.isRequired,
    })
  ).isRequired,
}

export default MessageList
