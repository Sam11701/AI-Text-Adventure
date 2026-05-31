import { useState, useRef, useEffect } from 'react'

export default function InputBar({ onSubmit, disabled, onContinue, onRetry, onErase }) {
  const [mode, setMode] = useState('Do')
  const [input, setInput] = useState('')
  const [inputOpen, setInputOpen] = useState(false)
  const textareaRef = useRef(null)

  useEffect(() => {
    if (inputOpen && textareaRef.current) {
      textareaRef.current.focus()
    }
  }, [inputOpen])

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + 'px'
    }
  }, [input])

  function buildAction() {
    const text = input.trim()
    if (!text) return null
    if (mode === 'Do') return `You ${text}`
    if (mode === 'Say') return `You say, "${text}"`
    return text
  }

  function handleSubmit() {
    const action = buildAction()
    if (!action) return
    onSubmit(action)
    setInput('')
    setInputOpen(false)
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
    if (e.key === 'Escape') {
      setInput('')
      setInputOpen(false)
    }
  }

  return (
    <div style={styles.container}>
      <div style={{
        maxHeight: inputOpen ? '200px' : '0px',
        opacity: inputOpen ? 1 : 0,
        overflow: 'hidden',
        transition: 'max-height 0.3s ease, opacity 0.2s ease',
      }}>
        <div style={styles.modeSwitcher}>
          {['Do', 'Say', 'Story'].map(m => (
            <button
              key={m}
              onClick={() => setMode(m)}
              disabled={disabled}
              style={{
                ...styles.modeButton,
                ...(mode === m ? styles.modeButtonActive : {}),
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
            style={styles.textarea}
          />
        </div>
      </div>

      <div style={styles.buttonRow}>
        <button
          onClick={() => setInputOpen(o => !o)}
          disabled={disabled}
          style={{ ...styles.actionButton, ...styles.takeATurnButton, opacity: disabled ? 0.5 : 1 }}
        >
          TAKE A TURN
        </button>
        <button onClick={onContinue} disabled={disabled} style={{ ...styles.actionButton, opacity: disabled ? 0.5 : 1 }}>
          CONTINUE
        </button>
        <button onClick={onRetry} disabled={disabled} style={{ ...styles.actionButton, opacity: disabled ? 0.5 : 1 }}>
          RETRY
        </button>
        <button onClick={onErase} disabled={disabled} style={{ ...styles.actionButton, opacity: disabled ? 0.5 : 1 }}>
          ERASE
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
    gap: '8px',
    maxWidth: '680px',
    margin: '0 auto 10px',
  },
  modeButton: {
    flex: 1,
    padding: '7px',
    background: '#222',
    color: '#666',
    border: '1px solid #333',
    borderRadius: '3px',
    fontSize: '12px',
    cursor: 'pointer',
  },
  modeButtonActive: {
    background: '#333',
    color: '#e8e8e8',
    borderColor: '#555',
  },
  inputGroup: {
    maxWidth: '680px',
    margin: '0 auto 10px',
  },
  textarea: {
    width: '100%',
    padding: '10px',
    fontSize: '14px',
    border: '1px solid #444',
    borderRadius: '3px',
    minHeight: '38px',
    maxHeight: '120px',
    backgroundColor: '#1a1a1a',
    color: '#e8e8e8',
    fontFamily: 'Georgia, serif',
    lineHeight: '1.4',
    resize: 'none',
    boxSizing: 'border-box',
  },
  buttonRow: {
    display: 'flex',
    gap: '8px',
    maxWidth: '680px',
    margin: '0 auto',
  },
  actionButton: {
    flex: 1,
    padding: '10px 8px',
    background: '#1a1a1a',
    color: '#e8e8e8',
    border: '1px solid #333',
    borderRadius: '4px',
    fontSize: '11px',
    letterSpacing: '0.5px',
    textTransform: 'uppercase',
    cursor: 'pointer',
  },
  takeATurnButton: {
    background: '#222',
  },
}
