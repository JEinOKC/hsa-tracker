/**
 * Transactions/Expenses Page - Main expense tracking interface
 */

import { useState } from 'react'
import { Link } from 'react-router-dom'
import TransactionForm from '../components/transactions/TransactionForm'
import TransactionList from '../components/transactions/TransactionList'

export default function Transactions() {
  const [refreshTrigger, setRefreshTrigger] = useState(0)
  const [showForm, setShowForm] = useState(false)

  const handleSuccess = () => {
    // Refresh the transaction list
    setRefreshTrigger((prev) => prev + 1)

    // Hide form after successful submission
    setShowForm(false)
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <header className="mb-8 flex items-center justify-between">
        <div>
          <Link to="/" className="text-blue-600 hover:text-blue-800 text-sm mb-2 inline-block">
            ← Back to Dashboard
          </Link>
          <h1 className="text-4xl font-bold text-gray-900">Expenses</h1>
          <p className="text-gray-600 mt-1">Track your HSA expenses and receipts</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium transition-colors"
        >
          {showForm ? 'Cancel' : 'Add Expense'}
        </button>
      </header>

      <div className="space-y-6">
        {/* Info Banner */}
        {!showForm && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h3 className="text-sm font-medium text-blue-900 mb-1">
              Track Your HSA Expenses
            </h3>
            <p className="text-sm text-blue-700">
              Add your medical expenses to track HSA-eligible purchases and manage reimbursements.
              Click "Add Expense" above to get started.
            </p>
          </div>
        )}

        {/* Add Expense Form */}
        {showForm && (
          <TransactionForm
            onSuccess={handleSuccess}
            onCancel={() => setShowForm(false)}
          />
        )}

        {/* Transactions List */}
        <TransactionList refreshTrigger={refreshTrigger} />

        {/* Quick Tip */}
        {!showForm && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h3 className="text-sm font-medium text-blue-900 mb-2">💡 Quick Tips</h3>
            <ul className="text-sm text-blue-700 list-disc list-inside space-y-1">
              <li>You can upload receipts after creating an expense</li>
              <li>Supported formats: JPEG, PNG, HEIC, and PDF</li>
              <li>Track reimbursement status for expenses paid out-of-pocket</li>
              <li>All HSA-eligible categories are pre-loaded for you</li>
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
