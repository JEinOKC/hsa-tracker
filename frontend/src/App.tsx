import { Routes, Route, NavLink } from 'react-router-dom'
import { ToastProvider } from './components/Toast'
import UpdatePrompt from './components/UpdatePrompt'
import { useAutoSync } from './hooks/useAutoSync'
import Dashboard from './pages/Dashboard'
import Transactions from './pages/Transactions'
import BankAccounts from './pages/BankAccounts'
import FamilyMembers from './pages/FamilyMembers'
import Login from './pages/Login'
import Register from './pages/Register'
import InvitePage from './pages/InvitePage'
import Settings from './pages/Settings'
import Rules from './pages/Rules'
import ProtectedRoute from './components/ProtectedRoute'

function Nav() {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-2 rounded-md text-sm font-medium transition-colors ${
      isActive ? 'bg-sky-700 text-white' : 'text-sky-100 hover:bg-sky-700 hover:text-white'
    }`

  const tabClass = ({ isActive }: { isActive: boolean }) =>
    `flex flex-col items-center gap-0.5 py-2 text-xs font-medium transition-colors flex-1 min-w-0 ${
      isActive ? 'text-sky-600' : 'text-gray-500'
    }`

  return (
    <>
      {/* Top bar */}
      <nav className="bg-sky-600 shadow-sm">
        <div className="container mx-auto px-4">
          <div className="flex items-center h-14 gap-1">
            <div className="flex items-center gap-2 mr-6">
              <img src="/favicon.svg" alt="" className="h-7 w-7" />
              <span className="text-white font-bold text-lg tracking-tight">HSA Tracker</span>
            </div>
            {/* Desktop nav links — hidden on mobile */}
            <div className="hidden md:flex items-center gap-1">
              <NavLink to="/" end className={linkClass}>Dashboard</NavLink>
              <NavLink to="/bank" className={linkClass}>Bank Accounts</NavLink>
              <NavLink to="/family" className={linkClass}>Family</NavLink>
              <NavLink to="/transactions" className={linkClass}>Transactions</NavLink>
              <NavLink to="/settings" className={linkClass}>Settings</NavLink>
            </div>
          </div>
        </div>
      </nav>

      {/* Bottom tab bar — mobile only */}
      <nav
        className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-white border-t border-gray-200 flex"
        style={{
          paddingBottom: 'env(safe-area-inset-bottom)',
          paddingLeft: 'env(safe-area-inset-left)',
          paddingRight: 'env(safe-area-inset-right)',
        }}
      >
        <NavLink to="/" end className={tabClass}>
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM14 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zM4 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1v-4zM14 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
          </svg>
          Dashboard
        </NavLink>
        <NavLink to="/bank" className={tabClass}>
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 10l9-7 9 7v11a1 1 0 01-1 1H4a1 1 0 01-1-1V10z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 21V12h6v9" />
          </svg>
          Bank
        </NavLink>
        <NavLink to="/family" className={tabClass}>
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          Family
        </NavLink>
        <NavLink to="/transactions" className={tabClass}>
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
          </svg>
          Transactions
        </NavLink>
        <NavLink to="/settings" className={tabClass}>
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          Settings
        </NavLink>
      </nav>
    </>
  )
}

function ProtectedLayout({ children }: { children: React.ReactNode }) {
  useAutoSync()
  return (
    <ProtectedRoute>
      <>
        <Nav />
        {/* Extra bottom padding on mobile so content clears the fixed tab bar */}
        <div className="pb-20 md:pb-0">
          {children}
        </div>
      </>
    </ProtectedRoute>
  )
}

function App() {
  return (
    <ToastProvider>
    <UpdatePrompt />
    <div className="min-h-screen bg-gray-50">
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/invite/:token" element={<InvitePage />} />

        <Route path="/" element={<ProtectedLayout><Dashboard /></ProtectedLayout>} />
        <Route path="/bank" element={<ProtectedLayout><BankAccounts /></ProtectedLayout>} />
        <Route path="/family" element={<ProtectedLayout><FamilyMembers /></ProtectedLayout>} />
        <Route path="/transactions" element={<ProtectedLayout><Transactions /></ProtectedLayout>} />
        <Route path="/settings" element={<ProtectedLayout><Settings /></ProtectedLayout>} />
        <Route path="/settings/rules" element={<ProtectedLayout><Rules /></ProtectedLayout>} />
      </Routes>
    </div>
    </ToastProvider>
  )
}

export default App
