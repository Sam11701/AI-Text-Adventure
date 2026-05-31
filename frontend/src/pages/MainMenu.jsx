import { useState, useEffect } from 'react'

export default function MainMenu({ onSelect }) {
  const [adventures, setAdventures] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [currentModel, setCurrentModel] = useState(null)
  const [availableModels, setAvailableModels] = useState([])
  const [showNewForm, setShowNewForm] = useState(false)
  const [newName, setNewName] = useState('')
  const [newPremise, setNewPremise] = useState('')
  const [creating, setCreating] = useState(false)
  const [showModelSelect, setShowModelSelect] = useState(false)

  useEffect(() => {
    fetchAdventures()
    fetchConfig()
  }, [])

  async function fetchAdventures() {
    try {
      const res = await fetch('/api/adventures')
      if (!res.ok) throw new Error('Failed to fetch adventures')
      const data = await res.json()
      setAdventures(data)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function fetchConfig() {
    try {
      const res = await fetch('/api/config')
      if (!res.ok) throw new Error('Failed to fetch config')
      const data = await res.json()
      setCurrentModel(data.model)
      setAvailableModels(data.models || [])
    } catch (err) {
      console.error('Failed to fetch config:', err)
    }
  }

  async function handleLoadAdventure(slug, name) {
    try {
      const res = await fetch(`/api/adventures/${slug}/load`, { method: 'POST' })
      if (!res.ok) throw new Error('Failed to load adventure')
      onSelect({ slug, name })
    } catch (err) {
      alert('Error loading adventure: ' + err.message)
    }
  }

  async function handleDeleteAdventure(slug, name) {
    if (!window.confirm(`Delete "${name}"?`)) return
    try {
      const res = await fetch(`/api/adventures/${slug}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('Failed to delete adventure')
      setAdventures(adventures.filter(a => a.slug !== slug))
    } catch (err) {
      alert('Error deleting adventure: ' + err.message)
    }
  }

  async function handleCreateAdventure(e) {
    e.preventDefault()
    if (!newName.trim() || !newPremise.trim()) {
      alert('Please fill in all fields')
      return
    }

    setCreating(true)
    try {
      const res = await fetch('/api/adventures', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newName,
          premise: newPremise
        })
      })
      if (!res.ok) throw new Error('Failed to create adventure')
      const data = await res.json()
      await fetchAdventures()
      setNewName('')
      setNewPremise('')
      setShowNewForm(false)
      onSelect({ slug: data.slug, name: newName.trim() })
    } catch (err) {
      alert('Error creating adventure: ' + err.message)
    } finally {
      setCreating(false)
    }
  }

  async function handleChangeModel(newModel) {
    try {
      const res = await fetch('/api/config/model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_id: newModel })
      })
      if (!res.ok) throw new Error('Failed to change model')
      setCurrentModel(newModel)
      setShowModelSelect(false)
    } catch (err) {
      alert('Error changing model: ' + err.message)
    }
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div style={styles.modelBar}>
          <span>Model: <strong>{currentModel || 'loading...'}</strong></span>
          <button
            onClick={() => setShowModelSelect(!showModelSelect)}
            style={styles.smallButton}
          >
            Change Model
          </button>
        </div>
        {showModelSelect && (
          <select
            value={currentModel}
            onChange={(e) => handleChangeModel(e.target.value)}
            style={styles.modelSelect}
          >
            {availableModels.map(m => (
              <option key={m[0]} value={m[0]}>{m[1]}</option>
            ))}
          </select>
        )}
      </div>

      <div style={styles.content}>
        <h1 style={styles.title}>AI Adventure</h1>

        {loading && <p style={styles.message}>Loading adventures...</p>}
        {error && <p style={styles.error}>Error: {error}</p>}

        {!loading && !error && (
          <>
            <button
              onClick={() => setShowNewForm(!showNewForm)}
              style={styles.newButton}
            >
              + New Adventure
            </button>

            {showNewForm && (
              <form onSubmit={handleCreateAdventure} style={styles.form}>
                <input
                  type="text"
                  placeholder="Adventure name"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  style={styles.input}
                  autoFocus
                />
                <textarea
                  placeholder="Starting premise..."
                  value={newPremise}
                  onChange={(e) => setNewPremise(e.target.value)}
                  style={styles.textarea}
                  rows="3"
                />
                <div style={styles.formButtons}>
                  <button type="submit" disabled={creating} style={styles.button}>
                    {creating ? 'Creating...' : 'Create'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowNewForm(false)}
                    style={{ ...styles.button, opacity: 0.6 }}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            )}

            <div style={styles.adventureList}>
              {adventures.length === 0 ? (
                <p style={styles.message}>No adventures yet. Create one to begin!</p>
              ) : (
                adventures.map(adv => (
                  <div key={adv.slug} style={styles.adventureCard}>
                    <div style={styles.adventureInfo}>
                      <h2 style={styles.adventureName}>{adv.meta.name}</h2>
                      <p style={styles.adventureMeta}>
                        Turns: {adv.meta.turn_counter || 0} | Last played: {adv.meta.last_played || 'never'}
                      </p>
                    </div>
                    <div style={styles.adventureActions}>
                      <button
                        onClick={() => handleLoadAdventure(adv.slug, adv.meta.name)}
                        style={styles.loadButton}
                      >
                        Continue
                      </button>
                      <button
                        onClick={() => handleDeleteAdventure(adv.slug, adv.meta.name)}
                        style={styles.deleteButton}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

const styles = {
  container: {
    minHeight: '100vh',
    display: 'flex',
    flexDirection: 'column',
    padding: '20px',
  },
  header: {
    textAlign: 'right',
    marginBottom: '40px',
    position: 'relative',
  },
  modelBar: {
    fontSize: '14px',
    color: '#aaa',
  },
  smallButton: {
    marginLeft: '12px',
    padding: '4px 12px',
    background: '#222',
    color: '#e8e8e8',
    border: '1px solid #333',
    borderRadius: '3px',
    fontSize: '12px',
  },
  modelSelect: {
    marginTop: '8px',
    padding: '6px',
    minWidth: '200px',
  },
  content: {
    flex: 1,
    maxWidth: '680px',
    margin: '0 auto',
    width: '100%',
  },
  title: {
    fontSize: '42px',
    textAlign: 'center',
    marginBottom: '40px',
    fontWeight: 'normal',
    letterSpacing: '2px',
  },
  message: {
    textAlign: 'center',
    color: '#666',
    marginBottom: '20px',
  },
  error: {
    textAlign: 'center',
    color: '#f88',
    marginBottom: '20px',
  },
  newButton: {
    display: 'block',
    margin: '0 auto 30px',
    padding: '10px 30px',
    background: '#222',
    color: '#e8e8e8',
    border: '1px solid #333',
    borderRadius: '3px',
    fontSize: '14px',
    transition: 'border-color 0.2s',
  },
  form: {
    background: '#1a1a1a',
    padding: '20px',
    borderRadius: '3px',
    marginBottom: '30px',
    border: '1px solid #333',
  },
  input: {
    width: '100%',
    marginBottom: '12px',
    padding: '10px',
    fontSize: '14px',
  },
  textarea: {
    width: '100%',
    marginBottom: '12px',
    padding: '10px',
    fontSize: '14px',
  },
  formButtons: {
    display: 'flex',
    gap: '10px',
  },
  button: {
    flex: 1,
    padding: '10px',
    background: '#222',
    color: '#e8e8e8',
    border: '1px solid #333',
    borderRadius: '3px',
    fontSize: '14px',
    cursor: 'pointer',
  },
  adventureList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '15px',
  },
  adventureCard: {
    background: '#1a1a1a',
    border: '1px solid #333',
    borderRadius: '3px',
    padding: '15px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  adventureInfo: {
    flex: 1,
  },
  adventureName: {
    fontSize: '18px',
    fontWeight: 'normal',
    marginBottom: '5px',
  },
  adventureMeta: {
    fontSize: '12px',
    color: '#666',
  },
  adventureActions: {
    display: 'flex',
    gap: '10px',
  },
  loadButton: {
    padding: '8px 16px',
    background: '#222',
    color: '#e8e8e8',
    border: '1px solid #333',
    borderRadius: '3px',
    fontSize: '12px',
    cursor: 'pointer',
  },
  deleteButton: {
    padding: '8px 16px',
    background: '#2a2222',
    color: '#f88',
    border: '1px solid #664',
    borderRadius: '3px',
    fontSize: '12px',
    cursor: 'pointer',
  },
}
