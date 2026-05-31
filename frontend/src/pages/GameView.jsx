import { useState, useEffect, useRef } from 'react'
import StoryFeed from '../components/StoryFeed'
import InputBar from '../components/InputBar'
import Sidebar from '../components/Sidebar'

export default function GameView({ adventure, onBack }) {
  const [premise, setPremise] = useState('')
  const [messages, setMessages] = useState([])
  const [streamingText, setStreamingText] = useState('')
  const [loading, setLoading] = useState(true)
  const [inputDisabled, setInputDisabled] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useEffect(() => {
    fetchState()
  }, [adventure.slug])

  async function fetchState() {
    try {
      const res = await fetch(`/api/adventures/${adventure.slug}/state`)
      if (!res.ok) throw new Error('Failed to fetch state')
      const data = await res.json()
      setPremise(data.premise)
      const recent = data.recent || []
      setMessages(recent.map((text, i) => ({ role: i % 2 === 0 ? 'player' : 'story', text })))
    } catch (err) {
      alert('Error loading adventure: ' + err.message)
      onBack()
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmit(action, display = action) {
    if (!action || !action.trim()) return

    setInputDisabled(true)
    setStreamingText('')

    if (display) setMessages(prev => [...prev, { role: 'player', text: display }])

    try {
      const response = await fetch(`/api/adventures/${adventure.slug}/turn`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action })
      })

      if (!response.ok) throw new Error('Failed to submit turn')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let currentParagraph = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim()
            if (!data) continue

            try {
              const event = JSON.parse(data)

              if (event.type === 'token') {
                currentParagraph += event.text
                setStreamingText(currentParagraph)
              } else if (event.type === 'status') {
                setStreamingText(event.text)
              } else if (event.type === 'error') {
                setStreamingText(`Error: ${event.text}`)
                setInputDisabled(false)
              } else if (event.type === 'done') {
                if (currentParagraph) {
                  setMessages(prev => [...prev, { role: 'story', text: currentParagraph }])
                }
                setStreamingText('')
                setInputDisabled(false)
              }
            } catch (e) {
              console.error('Failed to parse event:', e)
            }
          }
        }
      }
    } catch (err) {
      alert('Error: ' + err.message)
      setInputDisabled(false)
    }
  }

  async function handleContinue() {
    await handleSubmit('(no action - advance the scene by one beat; do not address the player)', null)
  }

  async function handleRetry() {
    setInputDisabled(true)
    setStreamingText('')
    setMessages(prev => prev.slice(0, -2))

    try {
      const response = await fetch(`/api/adventures/${adventure.slug}/retry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })

      if (!response.ok) throw new Error('Failed to retry')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let currentParagraph = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim()
            if (!data) continue

            try {
              const event = JSON.parse(data)

              if (event.type === 'token') {
                currentParagraph += event.text
                setStreamingText(currentParagraph)
              } else if (event.type === 'status') {
                setStreamingText(event.text)
              } else if (event.type === 'error') {
                setStreamingText(`Error: ${event.text}`)
                setInputDisabled(false)
              } else if (event.type === 'done') {
                if (currentParagraph) {
                  setMessages(prev => [...prev, { role: 'story', text: currentParagraph }])
                }
                setStreamingText('')
                setInputDisabled(false)
              }
            } catch (e) {
              console.error('Failed to parse event:', e)
            }
          }
        }
      }
    } catch (err) {
      alert('Error: ' + err.message)
      setInputDisabled(false)
    }
  }

  async function handleErase() {
    try {
      const res = await fetch(`/api/adventures/${adventure.slug}/undo`, { method: 'POST' })
      if (!res.ok) return
      setMessages(prev => prev.slice(0, -2))
    } catch (e) {
      console.error('Erase failed:', e)
    }
  }

  if (loading) {
    return (
      <div style={styles.container}>
        <div style={styles.loadingMessage}>Loading adventure...</div>
      </div>
    )
  }

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <button onClick={onBack} style={styles.backButton} title="Back to menu">
          ← Back
        </button>
        <h1 style={styles.adventureTitle}>{adventure.name}</h1>
        <button onClick={() => setSidebarOpen(true)} style={styles.cardsButton}>
          Cards
        </button>
      </div>

      {/* Premise */}
      {premise && (
        <div style={styles.premiseBox}>
          <p style={styles.premiseText}>{premise}</p>
        </div>
      )}

      {/* Story Feed */}
      <StoryFeed messages={messages} streamingText={streamingText} />

      {/* Input Bar */}
      <InputBar
        onSubmit={handleSubmit}
        disabled={inputDisabled}
        onContinue={handleContinue}
        onRetry={handleRetry}
        onErase={handleErase}
      />

      {/* Sidebar */}
      <Sidebar
        slug={adventure.slug}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
    </div>
  )
}

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    backgroundColor: '#111',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '15px 20px',
    borderBottom: '1px solid #333',
    backgroundColor: '#0a0a0a',
  },
  backButton: {
    background: 'none',
    border: 'none',
    color: '#e8e8e8',
    fontSize: '16px',
    cursor: 'pointer',
    padding: '5px 10px',
    transition: 'color 0.2s',
  },
  adventureTitle: {
    flex: 1,
    textAlign: 'center',
    fontSize: '20px',
    fontWeight: 'normal',
    color: '#e8e8e8',
  },
  cardsButton: {
    background: '#222',
    border: '1px solid #333',
    color: '#e8e8e8',
    padding: '6px 12px',
    borderRadius: '3px',
    fontSize: '12px',
    cursor: 'pointer',
  },
  premiseBox: {
    padding: '20px',
    borderBottom: '1px solid #333',
    backgroundColor: '#0f0f0f',
    maxWidth: '100%',
  },
  premiseText: {
    maxWidth: '680px',
    margin: '0 auto',
    fontSize: '14px',
    color: '#aaa',
    fontStyle: 'italic',
  },
  loadingMessage: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    fontSize: '16px',
    color: '#666',
  },
}
