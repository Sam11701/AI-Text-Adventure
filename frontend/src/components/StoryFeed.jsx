import { useEffect, useRef } from 'react'

export default function StoryFeed({ messages, streamingText }) {
  const feedRef = useRef(null)
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingText])

  return (
    <div style={styles.feed} ref={feedRef}>
      <div style={styles.content}>
        {messages.map((msg, idx) => (
          <div key={idx} style={msg.role === 'player' ? styles.playerMessage : styles.storyMessage}>
            {msg.text}
          </div>
        ))}

        {streamingText && (
          <div style={styles.streamingMessage}>
            {streamingText}
            <span style={styles.cursor}>▌</span>
          </div>
        )}

        <div ref={endRef} />
      </div>
    </div>
  )
}

const styles = {
  feed: {
    flex: 1,
    overflowY: 'auto',
    padding: '20px',
    backgroundColor: '#111',
  },
  content: {
    maxWidth: '680px',
    margin: '0 auto',
  },
  playerMessage: {
    color: '#888',
    marginBottom: '20px',
    fontStyle: 'italic',
    fontSize: '14px',
    lineHeight: '1.6',
  },
  storyMessage: {
    color: '#e8e8e8',
    marginBottom: '20px',
    fontSize: '15px',
    lineHeight: '1.7',
  },
  streamingMessage: {
    color: '#e8e8e8',
    marginBottom: '20px',
    fontSize: '15px',
    lineHeight: '1.7',
  },
  cursor: {
    display: 'inline-block',
    marginLeft: '2px',
    animation: 'blink 1s infinite',
  },
}

// Add keyframe animation via style tag
if (typeof document !== 'undefined') {
  const style = document.createElement('style')
  style.textContent = `
    @keyframes blink {
      0%, 50% { opacity: 1; }
      51%, 100% { opacity: 0; }
    }
  `
  document.head.appendChild(style)
}
