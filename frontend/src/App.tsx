import { Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Transactions from './pages/Transactions'
import BankAccounts from './pages/BankAccounts'
import FamilyMembers from './pages/FamilyMembers'
import Login from './pages/Login'
import Register from './pages/Register'
import InvitePage from './pages/InvitePage'
import ProtectedRoute from './components/ProtectedRoute'

function Nav() {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-2 rounded-md text-sm font-medium transition-colors ${
      isActive ? 'bg-sky-700 text-white' : 'text-sky-100 hover:bg-sky-700 hover:text-white'
    }`

  return (
    <nav className="bg-sky-600 shadow-sm">
      <div className="container mx-auto px-4">
        <div className="flex items-center h-14 gap-1">
          <div className="flex items-center gap-2 mr-6">
            <img src="/favicon.svg" alt="" className="h-7 w-7" />
            <span className="text-white font-bold text-lg tracking-tight">HSA Tracker</span>
          </div>
          <NavLink to="/" end className={linkClass}>Dashboard</NavLink>
          <NavLink to="/bank" className={linkClass}>Bank Accounts</NavLink>
          <NavLink to="/family" className={linkClass}>Family</NavLink>
          <NavLink to="/transactions" className={linkClass}>Transactions</NavLink>
        </div>
      </div>
    </nav>
  )
}

function ProtectedLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute>
      <>
        <Nav />
        {children}
      </>
    </ProtectedRoute>
  )
}

function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/invite/:token" element={<InvitePage />} />

        <Route path="/" element={<ProtectedLayout><Dashboard /></ProtectedLayout>} />
        <Route path="/bank" element={<ProtectedLayout><BankAccounts /></ProtectedLayout>} />
        <Route path="/family" element={<ProtectedLayout><FamilyMembers /></ProtectedLayout>} />
        <Route path="/transactions" element={<ProtectedLayout><Transactions /></ProtectedLayout>} />
      </Routes>
    </div>
  )
}

export default App
