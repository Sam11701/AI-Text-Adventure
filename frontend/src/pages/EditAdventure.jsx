import { useState, useEffect, useRef } from 'react'

const CATEGORIES = ['characters', 'classes', 'races', 'locations', 'factions', 'items', 'lore', 'other']
const CAT_LABEL = {
  characters: 'Character', classes: 'Class', races: 'Race', locations: 'Location',
  factions: 'Faction', items: 'Item', lore: 'Lore', other: 'Other',
}

const kebab = s => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'unnamed'

export default function EditAdventure({ adventure, onFinish }) {
  const [tab, setTab] = useState('plot')
  const [plotSaved, setPlotSaved] = useState(true)
  const [plot, setPlot] = useState({ story_summary: '', ai_instructions: '', plot_essentials: '', author_note: '' })
  const plotTimer = useRef(null)

  const [cards, setCards] = useState([])
  const [search, setSearch] = useState('')
  const [selectedCard, setSelectedCard] = useState(null)
  const [cardDraft, setCardDraft] = useState(null)
  const [cardSaved, setCardSaved] = useState(true)
  const cardTimer = useRef(null)
  const [collapsed, setCollapsed] = useState({})

  useEffect(() => {
    fetchPlot()
    fetchCards()
  }, [adventure.slug])

  async function fetchPlot() {
    const r = await fetch(`/api/adventures/${adventure.slug}/plot`)
    if (r.ok) setPlot(await r.json())
  }

  async function fetchCards() {
    const r = await fetch(`/api/adventures/${adventure.slug}/cards`)
    if (r.ok) setCards(await r.json())
  }

  function updatePlot(field, value) {
    const next = { ...plot, [field]: value }
    setPlot(next)
    setPlotSaved(false)
    clearTimeout(plotTimer.current)
    plotTimer.current = setTimeout(async () => {
      const r = await fetch(`/api/adventures/${adventure.slug}/plot`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(next),
      })
      if (r.ok) setPlotSaved(true)
    }, 800)
  }

  function selectCard(card) {
    setSelectedCard(card)
    setCardDraft({ ...card, triggers_str: (card.triggers || []).join(', ') })
    setCardSaved(true)
  }

  function updateCardDraft(field, value) {
    const next = { ...cardDraft, [field]: value }
    setCardDraft(next)
    setCardSaved(false)
    clearTimeout(cardTimer.current)
    cardTimer.current = setTimeout(() => persistCard(next), 800)
  }

  async function persistCard(draft) {
    const oldCat = selectedCard._category
    const oldSlug = kebab(selectedCard.name)
    const body = {
      name: draft.name,
      category: draft._category,
      entry: draft.entry || '',
      card_state: draft.state || '',
      triggers: (draft.triggers_str || '').split(',').map(t => t.trim()).filter(Boolean),
      notes: draft.notes || '',
      memory: draft.memory || [],
      goals: draft.goals || [],
      secrets: draft.secrets || [],
      plans: draft.plans || [],
      thoughts: draft.thoughts || '',
    }
    const r = await fetch(`/api/adventures/${adventure.slug}/cards/${oldCat}/${oldSlug}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (r.ok) {
      const data = await r.json()
      setCardSaved(true)
      setSelectedCard(prev => ({ ...prev, name: draft.name, _category: data.category }))
      fetchCards()
    }
  }

  async function deleteCard() {
    const cat = selectedCard._category
    const slug = kebab(selectedCard.name)
    await fetch(`/api/adventures/${adventure.slug}/cards/${cat}/${slug}`, { method: 'DELETE' })
    setSelectedCard(null)
    setCardDraft(null)
    fetchCards()
  }

  async function createCard() {
    const r = await fetch(`/api/adventures/${adventure.slug}/cards/new`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'New Card', category: 'other' }),
    })
    if (r.ok) {
      const r2 = await fetch(`/api/adventures/${adventure.slug}/cards`)
      if (r2.ok) {
        const all = await r2.json()
        setCards(all)
        const nc = all.find(c => c.name === 'New Card' && c._category === 'other')
        if (nc) selectCard(nc)
      }
    }
  }

  const grouped = CATEGORIES.reduce((acc, cat) => {
    const list = cards.filter(c => c._category === cat &&
      (!search || c.name.toLowerCase().includes(search.toLowerCase()) ||
        (c.entry || '').toLowerCase().includes(search.toLowerCase()))
    )
    if (list.length) acc[cat] = list
    return acc
  }, {})

  const totalCards = cards.length
  const isSaved = tab === 'plot' ? plotSaved : cardSaved

  if (selectedCard && tab === 'cards') {
    return (
      <div style={S.page}>
        <div style={S.header}>
          <button style={S.backIconBtn} onClick={() => { setSelectedCard(null); setCardDraft(null) }}>···</button>
          <span style={S.cardDetailTitle}>{cardDraft?.name || selectedCard.name}</span>
          <button style={S.finishBtn} onClick={onFinish}>FINISH</button>
        </div>
        <CardDetail
          card={cardDraft}
          saved={cardSaved}
          onChange={updateCardDraft}
          onDelete={deleteCard}
        />
      </div>
    )
  }

  return (
    <div style={S.page}>
      <div style={S.header}>
        <div style={S.headerLeft}>
          <span style={S.headerIcon}>◈</span>
          <span style={S.headerTitle}>Edit Adventure</span>
          <span style={S.savedChip}>{isSaved ? '✓ Saved' : '...'}</span>
        </div>
        <button style={S.finishBtn} onClick={onFinish}>FINISH</button>
      </div>

      <div style={S.tabBar}>
        {[
          ['plot', '≡', 'PLOT', null],
          ['cards', '⊞', 'STORY CARDS', totalCards || null],
          ['details', '☰', 'DETAILS', null],
        ].map(([key, icon, label, count]) => (
          <button key={key} style={tab === key ? S.tabActive : S.tab} onClick={() => setTab(key)}>
            <span style={S.tabIcon}>{icon}</span>
            {label}
            {count != null && <span style={S.badge}>{count}</span>}
          </button>
        ))}
      </div>

      <div style={S.content}>
        {tab === 'plot' && <PlotTab plot={plot} onChange={updatePlot} />}
        {tab === 'cards' && (
          <CardsTab
            grouped={grouped}
            search={search}
            onSearch={setSearch}
            onSelect={selectCard}
            onCreate={createCard}
            collapsed={collapsed}
            onToggle={cat => setCollapsed(p => ({ ...p, [cat]: !p[cat] }))}
          />
        )}
        {tab === 'details' && <DetailsTab adventure={adventure} />}
      </div>
    </div>
  )
}

function PlotTab({ plot, onChange }) {
  const sections = [
    {
      key: 'ai_instructions',
      label: 'AI Instructions',
      placeholder: 'Custom narrator instructions. Overrides the default narrator prompt when set.',
    },
    {
      key: 'story_summary',
      label: 'Story Summary',
      placeholder: 'The premise and overview of your adventure.',
    },
    {
      key: 'plot_essentials',
      label: 'Plot Essentials',
      placeholder: 'Key details: player character info, world rules, important context.',
    },
    {
      key: 'author_note',
      label: "Author's Note",
      placeholder: 'Tone, style, and atmosphere guidance appended to every turn.',
    },
  ]

  return (
    <div style={S.plotTab}>
      {sections.map(({ key, label, placeholder }) => (
        <div key={key} style={S.plotSection}>
          <div style={S.sectionHeader}>
            <span style={S.sectionLabel}>{label}</span>
            <button
              style={S.clearBtn}
              onClick={() => onChange(key, '')}
              title="Clear"
            >
              🗑
            </button>
          </div>
          <textarea
            style={S.plotTextarea}
            value={plot[key] || ''}
            onChange={e => onChange(key, e.target.value)}
            placeholder={placeholder}
          />
        </div>
      ))}
    </div>
  )
}

function CardsTab({ grouped, search, onSearch, onSelect, onCreate, collapsed, onToggle }) {
  const isEmpty = Object.keys(grouped).length === 0

  return (
    <div style={S.cardsTab}>
      <div style={S.searchRow}>
        <div style={S.searchWrapper}>
          <span style={S.searchIcon}>⌕</span>
          <input
            style={S.searchInput}
            placeholder="Search"
            value={search}
            onChange={e => onSearch(e.target.value)}
          />
        </div>
      </div>

      <div style={S.cardsActions}>
        <button style={S.createCardBtn} onClick={onCreate}>+ CREATE STORY CARD</button>
      </div>

      {isEmpty ? (
        <div style={S.empty}>
          {search ? 'No cards match your search.' : 'No story cards yet.'}
        </div>
      ) : (
        Object.entries(grouped).map(([cat, list]) => (
          <div key={cat} style={S.catGroup}>
            <div style={S.catHeader} onClick={() => onToggle(cat)}>
              <span style={S.catLabel}>{CAT_LABEL[cat]}</span>
              <span style={S.catCount}>{list.length}</span>
              <span style={S.collapseArrow}>{collapsed[cat] ? '▼' : '▲'}</span>
            </div>
            {!collapsed[cat] && (
              <div style={S.cardGrid}>
                {list.map((card, i) => (
                  <div key={i} style={S.cardTile} onClick={() => onSelect(card)}>
                    <div style={S.cardTileName}>{card.name}</div>
                    <div style={S.cardTileEntry}>{card.entry}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))
      )}
    </div>
  )
}

function CardDetail({ card, saved, onChange, onDelete }) {
  const [subTab, setSubTab] = useState('details')
  if (!card) return null

  const entryLen = (card.entry || '').length
  const ENTRY_MAX = 1000

  return (
    <div style={S.cardDetailWrap}>
      <div style={S.cardDetailSubTabs}>
        <button style={subTab === 'details' ? S.subTabActive : S.subTab} onClick={() => setSubTab('details')}>
          DETAILS
        </button>
        <button style={subTab === 'command' ? S.subTabActive : S.subTab} onClick={() => setSubTab('command')}>
          COMMAND
        </button>
        <span style={S.cardSavedChip}>{saved ? '✓ Saved' : '...'}</span>
      </div>

      <div style={S.cardDetailFields}>
        {subTab === 'details' && (
          <>
            <div style={S.fieldGroup}>
              <label style={S.fieldLabel}>TYPE</label>
              <select
                style={S.select}
                value={card._category || 'other'}
                onChange={e => onChange('_category', e.target.value)}
              >
                {CATEGORIES.map(cat => (
                  <option key={cat} value={cat}>{CAT_LABEL[cat]}</option>
                ))}
              </select>
            </div>

            <div style={S.fieldGroup}>
              <label style={S.fieldLabel}>NAME</label>
              <input
                style={S.input}
                value={card.name || ''}
                onChange={e => onChange('name', e.target.value)}
              />
              <div style={S.fieldHint}>
                Generation uses the title above plus the current Story Card Command.
              </div>
            </div>

            <div style={S.fieldGroup}>
              <div style={S.entryHeader}>
                <label style={S.fieldLabel}>ENTRY</label>
                <span style={S.charCount}>{entryLen} / {ENTRY_MAX}</span>
              </div>
              <textarea
                style={{ ...S.textarea, minHeight: 180 }}
                value={card.entry || ''}
                onChange={e => onChange('entry', e.target.value)}
                maxLength={ENTRY_MAX}
              />
            </div>

            <div style={S.fieldGroup}>
              <label style={S.fieldLabel}>TRIGGERS</label>
              <input
                style={S.input}
                value={card.triggers_str || ''}
                onChange={e => onChange('triggers_str', e.target.value)}
                placeholder="Comma-separated words that activate this card"
              />
            </div>

            <div style={S.fieldGroup}>
              <label style={S.fieldLabel}>NOTES</label>
              <textarea
                style={S.textarea}
                value={card.notes || ''}
                onChange={e => onChange('notes', e.target.value)}
                placeholder="Notes for this story element. These are not visible to the AI but will be visible to players during character creation."
              />
            </div>

            <button style={S.deleteBtn} onClick={onDelete}>Delete Card</button>
          </>
        )}

        {subTab === 'command' && (
          <p style={{ color: '#666', fontSize: 13, lineHeight: 1.6 }}>
            Story Card Commands let you define how this card influences the story. Coming soon.
          </p>
        )}
      </div>
    </div>
  )
}

function DetailsTab({ adventure }) {
  return (
    <div style={S.detailsTab}>
      <div style={S.fieldGroup}>
        <label style={S.fieldLabel}>ADVENTURE NAME</label>
        <div style={{ ...S.input, color: '#888', userSelect: 'text' }}>{adventure.name}</div>
      </div>
    </div>
  )
}

const S = {
  page: {
    display: 'flex', flexDirection: 'column', height: '100vh',
    backgroundColor: '#111', color: '#e8e8e8',
  },

  header: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '12px 16px', backgroundColor: '#181818',
    borderBottom: '1px solid #2a2a2a', flexShrink: 0,
  },
  headerLeft: { display: 'flex', alignItems: 'center', gap: 10 },
  headerIcon: { fontSize: 16, opacity: 0.6 },
  headerTitle: { fontSize: 15, fontWeight: 500 },
  savedChip: {
    fontSize: 11, color: '#888', background: '#222',
    padding: '2px 8px', borderRadius: 10, border: '1px solid #333',
  },
  finishBtn: {
    background: '#e6a817', color: '#000', border: 'none',
    padding: '7px 18px', borderRadius: 4, fontSize: 12,
    fontWeight: 700, cursor: 'pointer', letterSpacing: 1,
  },
  backIconBtn: {
    background: 'none', border: 'none', color: '#888',
    fontSize: 20, cursor: 'pointer', padding: '4px 10px', letterSpacing: 2,
  },
  cardDetailTitle: { flex: 1, textAlign: 'center', fontSize: 15, fontWeight: 500 },

  tabBar: {
    display: 'flex', padding: '0 8px', backgroundColor: '#181818',
    borderBottom: '1px solid #2a2a2a', flexShrink: 0,
  },
  tab: {
    background: 'none', border: 'none', borderBottom: '2px solid transparent',
    color: '#777', fontSize: 11, fontWeight: 600, padding: '10px 14px',
    cursor: 'pointer', letterSpacing: 0.8, display: 'flex', alignItems: 'center', gap: 5,
  },
  tabActive: {
    background: 'none', border: 'none', borderBottom: '2px solid #e6a817',
    color: '#e8e8e8', fontSize: 11, fontWeight: 600, padding: '10px 14px',
    cursor: 'pointer', letterSpacing: 0.8, display: 'flex', alignItems: 'center', gap: 5,
  },
  tabIcon: { opacity: 0.7 },
  badge: {
    background: '#2d5fa6', color: '#fff', fontSize: 10,
    padding: '1px 6px', borderRadius: 8, fontWeight: 700,
  },

  content: { flex: 1, overflowY: 'auto' },

  plotTab: {
    padding: 16, display: 'flex', flexDirection: 'column', gap: 10,
    maxWidth: 700, margin: '0 auto', width: '100%', boxSizing: 'border-box',
  },
  plotSection: {
    background: '#1a1a1a', border: '1px solid #2a2a2a', borderRadius: 4,
  },
  sectionHeader: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '8px 12px 6px', borderBottom: '1px solid #252525',
  },
  sectionLabel: {
    fontSize: 11, color: '#777', textTransform: 'uppercase',
    letterSpacing: 1, fontWeight: 600,
  },
  clearBtn: {
    background: 'none', border: 'none', color: '#444',
    cursor: 'pointer', fontSize: 13, padding: '2px 4px',
  },
  plotTextarea: {
    display: 'block', width: '100%', background: 'transparent',
    border: 'none', color: '#d0d0d0', fontSize: 13, lineHeight: 1.65,
    padding: '10px 12px', resize: 'vertical', outline: 'none',
    boxSizing: 'border-box', minHeight: 90, fontFamily: 'inherit',
  },

  cardsTab: { padding: '12px 16px' },
  searchRow: { marginBottom: 10 },
  searchWrapper: {
    display: 'flex', alignItems: 'center', background: '#1c1c1c',
    border: '1px solid #333', borderRadius: 4, padding: '7px 10px', gap: 8,
  },
  searchIcon: { color: '#555', fontSize: 16 },
  searchInput: {
    background: 'none', border: 'none', color: '#e8e8e8',
    fontSize: 13, flex: 1, outline: 'none',
  },
  cardsActions: {
    display: 'flex', alignItems: 'center', marginBottom: 16, marginTop: 4,
  },
  createCardBtn: {
    background: 'none', border: '1px solid #e6a817', color: '#e6a817',
    fontSize: 11, fontWeight: 700, letterSpacing: 1,
    padding: '6px 12px', borderRadius: 3, cursor: 'pointer',
  },
  catGroup: { marginBottom: 18 },
  catHeader: {
    display: 'flex', alignItems: 'center', gap: 8,
    padding: '4px 0 8px', cursor: 'pointer', borderBottom: '1px solid #252525',
    marginBottom: 10,
  },
  catLabel: { fontSize: 14, fontWeight: 700 },
  catCount: { fontSize: 13, color: '#888' },
  collapseArrow: { marginLeft: 'auto', color: '#555', fontSize: 11 },
  cardGrid: { display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 },
  cardTile: {
    background: '#1c1c1c', border: '1px solid #2a2a2a', borderRadius: 4,
    padding: 12, cursor: 'pointer',
  },
  cardTileName: { fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#e8e8e8' },
  cardTileEntry: {
    fontSize: 12, color: '#777', overflow: 'hidden',
    display: '-webkit-box', WebkitLineClamp: 4, WebkitBoxOrient: 'vertical',
    lineHeight: 1.5,
  },
  empty: { color: '#555', fontSize: 13, padding: '40px 0', textAlign: 'center' },

  cardDetailWrap: { flex: 1, display: 'flex', flexDirection: 'column', overflowY: 'auto' },
  cardDetailSubTabs: {
    display: 'flex', alignItems: 'center', padding: '10px 16px', gap: 8,
    borderBottom: '1px solid #2a2a2a', backgroundColor: '#181818', flexShrink: 0,
  },
  subTab: {
    background: '#252525', border: 'none', color: '#777',
    fontSize: 11, fontWeight: 700, padding: '6px 14px',
    borderRadius: 12, cursor: 'pointer', letterSpacing: 0.8,
  },
  subTabActive: {
    background: '#333', border: 'none', color: '#e8e8e8',
    fontSize: 11, fontWeight: 700, padding: '6px 14px',
    borderRadius: 12, cursor: 'pointer', letterSpacing: 0.8,
  },
  cardSavedChip: { marginLeft: 'auto', fontSize: 11, color: '#666' },
  cardDetailFields: {
    padding: 16, display: 'flex', flexDirection: 'column', gap: 18,
    maxWidth: 560, margin: '0 auto', width: '100%', boxSizing: 'border-box',
  },

  fieldGroup: { display: 'flex', flexDirection: 'column', gap: 6 },
  fieldLabel: {
    fontSize: 11, color: '#666', textTransform: 'uppercase',
    letterSpacing: 1, fontWeight: 600,
  },
  fieldHint: { fontSize: 11, color: '#555', marginTop: 2 },
  entryHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  charCount: { fontSize: 11, color: '#3a7bd5' },

  input: {
    background: '#1c1c1c', border: '1px solid #2e2e2e', color: '#e8e8e8',
    fontSize: 13, padding: '9px 11px', borderRadius: 4, outline: 'none',
    width: '100%', boxSizing: 'border-box', fontFamily: 'inherit',
  },
  select: {
    background: '#1c1c1c', border: '1px solid #2e2e2e', color: '#e8e8e8',
    fontSize: 13, padding: '9px 11px', borderRadius: 4, outline: 'none',
    width: '100%', boxSizing: 'border-box', cursor: 'pointer',
  },
  textarea: {
    background: '#1c1c1c', border: '1px solid #2e2e2e', color: '#e8e8e8',
    fontSize: 13, padding: '9px 11px', borderRadius: 4, outline: 'none',
    width: '100%', boxSizing: 'border-box', resize: 'vertical',
    minHeight: 80, lineHeight: 1.65, fontFamily: 'inherit',
  },
  deleteBtn: {
    background: 'none', border: '1px solid #8b3333', color: '#c44',
    fontSize: 12, padding: '7px 14px', borderRadius: 3,
    cursor: 'pointer', alignSelf: 'flex-start',
  },

  detailsTab: {
    padding: 16, maxWidth: 560, margin: '0 auto',
    width: '100%', boxSizing: 'border-box',
  },
}
