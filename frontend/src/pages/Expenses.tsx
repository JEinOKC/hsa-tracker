/**
 * Expenses Page - Main expense tracking interface
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import TransactionForm from '../components/transactions/TransactionForm'
import TransactionList from '../components/transactions/TransactionList'

export default function Expenses() {
  const [refreshTrigger, setRefreshTrigger] = useState(0)
  const [showForm, setShowForm] = useState(true)
  const navigate = useNavigate()

  const handleSuccess = () => {
    // Refresh the transaction list
    setRefreshTrigger((prev) => prev + 1)

    // Optionally hide form after successful submission
    // setShowForm(false)
  }

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">HSA Tracker</h1>
              <p className="text-sm text-gray-600 mt-1">Track your health savings account expenses</p>
            </div>
            <div className="flex items-center gap-4">
              <button
                onClick={() => setShowForm(!showForm)}
                className="px-4 py-2 text-sm font-medium text-blue-600 hover:text-blue-800"
              >
                {showForm ? 'Hide Form' : 'Add Expense'}
              </button>
              <button
                onClick={handleLogout}
                className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-800"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-8">
          {/* Info Banner */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h3 className="text-sm font-medium text-blue-900 mb-1">
              Track Your HSA Expenses
            </h3>
            <p className="text-sm text-blue-700">
              Add your medical expenses below to track HSA-eligible purchases and manage reimbursements.
              Your data is securely stored and receipts are saved to your private S3 bucket.
            </p>
          </div>

          {/* Add Expense Form */}
          {showForm && (
            <TransactionForm onSuccess={handleSuccess} />
          )}

          {/* Transactions List */}
          <TransactionList refreshTrigger={refreshTrigger} />
        </div>
      </main>

      {/* Footer */}
      <footer className="mt-12 bg-white border-t border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <p className="text-center text-sm text-gray-500">
            HSA Tracker - Self-hosted expense tracking for families
          </p>
        </div>
      </footer>
    </div>
  )
}
