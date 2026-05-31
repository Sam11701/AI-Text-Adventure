import { useState } from 'react'
import MainMenu from './pages/MainMenu'
import GameView from './pages/GameView'

export default function App() {
  const [adventure, setAdventure] = useState(null) // {slug, name}

  if (adventure) {
    return <GameView adventure={adventure} onBack={() => setAdventure(null)} />
  }
  return <MainMenu onSelect={setAdventure} />
}
