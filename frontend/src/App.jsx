import { useState } from 'react'
import MainMenu from './pages/MainMenu'
import GameView from './pages/GameView'
import EditAdventure from './pages/EditAdventure'

export default function App() {
  const [adventure, setAdventure] = useState(null)
  const [editing, setEditing] = useState(false)

  if (adventure && editing) {
    return <EditAdventure adventure={adventure} onFinish={() => setEditing(false)} />
  }
  if (adventure) {
    return (
      <GameView
        adventure={adventure}
        onBack={() => { setAdventure(null); setEditing(false) }}
        onEdit={() => setEditing(true)}
      />
    )
  }
  return <MainMenu onSelect={setAdventure} />
}
