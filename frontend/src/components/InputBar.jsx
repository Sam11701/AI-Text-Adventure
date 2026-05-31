import { useState, useRef, useEffect } from 'react'

export default function InputBar({ onSubmit, disabled }) {
  const [mode, setMode] = useState('Do') // Do | Say | Story
  const [input, setInput] = useState('')
  const textareaRef = useRef(null)

  // Auto-size textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      const scrollHeight = Math.min(textareaRef.current.scrollHeight, 120) // max 4 lines ~30px each
      textareaRef.current.style.height = scrollHeight + 'px'
    }
  }, [input])

  function buildAction() {
    const text = input.trim()
    if (!text) return null

    if (mode === 'Do') {
      return `You ${text}`
    } else if (mode === 'Say') {
      return `You say, "${text}"`
    } else {
      return text
    }
  }

  function handleSubmit() {
    const action = buildAction()
    if (!action) return

    onSubmit(action)
    setInput('')
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div style={styles.container}>
      <div style={styles.modeSwitcher}>
        {['Do', 'Say', 'Story'].map(m => (
          <button
            key={m}
            onClick={() => setMode(m)}
            disabled={disabled}
            style={{
              ...styles.modeButton,
              ...(mode === m ? styles.modeButtonActive : {}),
              opacity: disabled ? 0.5 : 1,
            }}
          >
            {m}
          </button>
        ))}
      </div>

      <div style={styles.inputGroup}>
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder="What do you do?"
          style={{
            ...styles.textarea,
            opacity: disabled ? 0.6 : 1,
          }}
        />
        <button
          onClick={handleSubmit}
          disabled={disabled || !input.trim()}
          style={{
            ...styles.submitButton,
            opacity: disabled || !input.trim() ? 0.5 : 1,
          }}
        >
          Submit
        </button>
      </div>
    </div>
  )
}

const styles = {
  container: {
    borderTop: '1px solid #333',
    backgroundColor: '#0a0a0a',
    padding: '15px 20px',
  },
  modeSwitcher: {
    display: 'flex',
    gap: '10px',
    marginBottom: '12px',
    maxWidth: '680px',
    margin: '0 auto 12px',
  },
  modeButton: {
    flex: 1,
    padding: '8px',
    background: '#222',
    color: '#666',
    border: '1px solid #333',
    borderRadius: '3px',
    fontSize: '12px',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  modeButtonActive: {
    background: '#333',
    color: '#e8e8e8',
    borderColor: '#555',
  },
  inputGroup: {
    display: 'flex',
    gap: '10px',
    maxWidth: '680px',
    margin: '0 auto',
  },
  textarea: {
    flex: 1,
    padding: '10px',
    fontSize: '14px',
    border: '1px solid #333',
    borderRadius: '3px',
    minHeight: '36px',
    maxHeight: '120px',
    backgroundColor: '#1a1a1a',
    color: '#e8e8e8',
    fontFamily: 'Georgia, serif',
    lineHeight: '1.4',
  },
  submitButton: {
    padding: '10px 20px',
    background: '#222',
    color: '#e8e8e8',
    border: '1px solid #333',
    borderRadius: '3px',
    fontSize: '14px',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
}
