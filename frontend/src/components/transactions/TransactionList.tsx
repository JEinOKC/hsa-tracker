/**
 * Transaction/Expense List Component
 */

import { useState, useEffect } from 'react'
import transactionService from '../../services/transaction'
import type {
  Transaction,
  Category,
  FamilyMember,
  TransactionFilters,
} from '../../types/transaction'
import {
  getPaymentMethodLabel,
  getReimbursementStatusLabel,
  getReimbursementStatusColor,
} from '../../types/transaction'

interface TransactionListProps {
  refreshTrigger?: number // Change this to trigger a refresh
  onEdit?: (transaction: Transaction) => void
}

export default function TransactionList({ refreshTrigger, onEdit }: TransactionListProps) {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [familyMembers, setFamilyMembers] = useState<FamilyMember[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  // Filters
  const [filters, setFilters] = useState<TransactionFilters>({
    skip: 0,
    limit: 50,
  })

  // Load data on mount and when refreshTrigger changes
  useEffect(() => {
    loadData()
  }, [refreshTrigger, filters])

  const loadData = async () => {
    setIsLoading(true)
    setError('')

    try {
      const [transactionsData, categoriesData, membersData] = await Promise.all([
        transactionService.listTransactions(filters),
        transactionService.listCategories(),
        transactionService.getFamilyMembers(),
      ])

      setTransactions(transactionsData.transactions)
      setTotal(transactionsData.total)
      setCategories(categoriesData)
      setFamilyMembers(membersData)
    } catch (err: any) {
      console.error('Failed to load transactions:', err)
      setError(err.response?.data?.detail || 'Failed to load expenses')
    } finally {
      setIsLoading(false)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this expense?')) {
      return
    }

    try {
      await transactionService.deleteTransaction(id)
      loadData() // Reload list
    } catch (err: any) {
      console.error('Failed to delete transaction:', err)
      alert(err.response?.data?.detail || 'Failed to delete expense')
    }
  }

  const getCategoryName = (categoryId: string): string => {
    const category = categories.find((c) => c.id === categoryId)
    return category?.name || 'Unknown'
  }

  const getFamilyMemberName = (memberId: string): string => {
    const member = familyMembers.find((m) => m.id === memberId)
    return member?.name || 'Unknown'
  }

  const formatCurrency = (amount: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount)
  }

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="text-center text-gray-500">Loading expenses...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      </div>
    )
  }

  if (transactions.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="text-center text-gray-500 py-8">
          <p className="text-lg mb-2">No expenses yet</p>
          <p className="text-sm">Add your first expense using the form above!</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-200">
        <h2 className="text-xl font-bold text-gray-900">
          Recent Expenses ({total})
        </h2>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Date
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Member
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Category
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Merchant
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Amount
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Payment
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {transactions.map((transaction) => (
              <tr key={transaction.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  {formatDate(transaction.transaction_date)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  {getFamilyMemberName(transaction.family_member_id)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  {getCategoryName(transaction.category_id)}
                </td>
                <td className="px-6 py-4 text-sm text-gray-900">
                  {transaction.merchant_name || '—'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 text-right font-medium">
                  {formatCurrency(transaction.amount)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                  {getPaymentMethodLabel(transaction.payment_method)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span
                    className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${getReimbursementStatusColor(
                      transaction.reimbursement_status
                    )}`}
                  >
                    {getReimbursementStatusLabel(transaction.reimbursement_status)}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <button
                    onClick={() => onEdit && onEdit(transaction)}
                    className="text-blue-600 hover:text-blue-800 mr-3"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(transaction.id)}
                    className="text-red-600 hover:text-red-800"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Summary */}
      <div className="px-6 py-4 border-t border-gray-200 bg-gray-50">
        <div className="flex justify-between items-center">
          <p className="text-sm text-gray-600">
            Showing {transactions.length} of {total} expenses
          </p>
          <div className="text-right">
            <p className="text-sm text-gray-600">Total Amount</p>
            <p className="text-xl font-bold text-gray-900">
              {formatCurrency(
                transactions.reduce((sum, t) => sum + Number(t.amount), 0)
              )}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
