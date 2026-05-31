import { useState, useEffect } from 'react'

export default function Sidebar({ slug, open, onClose }) {
  const [cards, setCards] = useState({})
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (open) {
      fetchCards()
    }
  }, [open, slug])

  async function fetchCards() {
    setLoading(true)
    try {
      const res = await fetch(`/api/adventures/${slug}/cards`)
      if (!res.ok) throw new Error('Failed to fetch cards')
      const data = await res.json()
      setCards(data)
    } catch (err) {
      console.error('Error fetching cards:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      {/* Overlay */}
      {open && (
        <div
          style={styles.overlay}
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <div
        style={{
          ...styles.sidebar,
          transform: open ? 'translateX(0)' : 'translateX(100%)',
        }}
      >
        <div style={styles.header}>
          <h2 style={styles.title}>Cards</h2>
          <button onClick={onClose} style={styles.closeButton}>
            ✕
          </button>
        </div>

        <div style={styles.content}>
          {loading ? (
            <p style={styles.loading}>Loading cards...</p>
          ) : Object.keys(cards).length === 0 ? (
            <p style={styles.empty}>No cards yet.</p>
          ) : (
            Object.entries(cards).map(([category, cardList]) => (
              <div key={category} style={styles.section}>
                <h3 style={styles.sectionTitle}>{category}</h3>
                <ul style={styles.cardList}>
                  {cardList.map((card, idx) => (
                    <li key={idx} style={styles.card}>
                      {card}
                    </li>
                  ))}
                </ul>
              </div>
            ))
          )}
        </div>
      </div>
    </>
  )
}

const styles = {
  overlay: {
    position: 'fixed',
    inset: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    zIndex: 98,
  },
  sidebar: {
    position: 'fixed',
    right: 0,
    top: 0,
    bottom: 0,
    width: '300px',
    backgroundColor: '#0a0a0a',
    borderLeft: '1px solid #333',
    zIndex: 99,
    display: 'flex',
    flexDirection: 'column',
    transition: 'transform 0.3s ease',
    overflowY: 'auto',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '15px 20px',
    borderBottom: '1px solid #333',
  },
  title: {
    fontSize: '18px',
    fontWeight: 'normal',
  },
  closeButton: {
    background: 'none',
    border: 'none',
    color: '#e8e8e8',
    fontSize: '20px',
    cursor: 'pointer',
    padding: 0,
  },
  content: {
    flex: 1,
    padding: '20px',
    overflowY: 'auto',
  },
  loading: {
    color: '#666',
    fontSize: '14px',
  },
  empty: {
    color: '#666',
    fontSize: '14px',
  },
  section: {
    marginBottom: '25px',
  },
  sectionTitle: {
    fontSize: '12px',
    color: '#888',
    textTransform: 'uppercase',
    letterSpacing: '1px',
    marginBottom: '10px',
    fontWeight: 'normal',
  },
  cardList: {
    listStyle: 'none',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  card: {
    fontSize: '13px',
    color: '#e8e8e8',
    padding: '8px',
    backgroundColor: '#1a1a1a',
    borderRadius: '3px',
    border: '1px solid #333',
  },
}
