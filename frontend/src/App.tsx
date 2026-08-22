import { Navigate, Route, Routes } from 'react-router-dom'
import Home from './pages/Home'
import Search from './pages/Search'
import RouteList from './pages/RouteList'
import RouteDetail from './pages/RouteDetail'
import Guide from './pages/Guide'
import MapScreen from './pages/MapScreen'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/search" element={<Search />} />
      <Route path="/map" element={<MapScreen />} />
      <Route path="/routes" element={<RouteList />} />
      <Route path="/routes/:id" element={<RouteDetail />} />
      <Route path="/guide/:id" element={<Guide />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
