/**
 * Transaction/Expense Entry Form
 */

import { useState, useEffect } from 'react'
import transactionService from '../../services/transaction'
import type {
  TransactionCreate,
  Category,
  FamilyMember,
  PaymentMethod,
  ReimbursementStatus,
} from '../../types/transaction'
import {
  PaymentMethod as PM,
  ReimbursementStatus as RS,
  getPaymentMethodLabel,
  getReimbursementStatusLabel,
} from '../../types/transaction'

interface TransactionFormProps {
  onSuccess?: () => void
  onCancel?: () => void
}

export default function TransactionForm({ onSuccess, onCancel }: TransactionFormProps) {
  const [categories, setCategories] = useState<Category[]>([])
  const [familyMembers, setFamilyMembers] = useState<FamilyMember[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  // Form fields
  const [formData, setFormData] = useState<TransactionCreate>({
    family_member_id: '',
    category_id: '',
    transaction_date: new Date().toISOString().split('T')[0], // Today's date
    amount: 0,
    merchant_name: '',
    description: '',
    payment_method: PM.PERSONAL,
    reimbursement_status: RS.PENDING,
  })

  // Load categories and family members on mount
  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [categoriesData, membersData] = await Promise.all([
        transactionService.listCategories(),
        transactionService.getFamilyMembers(),
      ])

      setCategories(categoriesData)
      setFamilyMembers(membersData)

      // Auto-select first family member if available
      if (membersData.length > 0 && !formData.family_member_id) {
        setFormData((prev) => ({
          ...prev,
          family_member_id: membersData[0].id,
        }))
      }
    } catch (err: any) {
      console.error('Failed to load data:', err)
      setError(err.response?.data?.detail || 'Failed to load form data')
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      // Validate required fields
      if (!formData.family_member_id) {
        setError('Please select a family member')
        setIsLoading(false)
        return
      }

      if (!formData.category_id) {
        setError('Please select a category')
        setIsLoading(false)
        return
      }

      if (formData.amount <= 0) {
        setError('Amount must be greater than 0')
        setIsLoading(false)
        return
      }

      // Create transaction
      await transactionService.createTransaction(formData)

      // Reset form
      setFormData({
        family_member_id: familyMembers[0]?.id || '',
        category_id: '',
        transaction_date: new Date().toISOString().split('T')[0],
        amount: 0,
        merchant_name: '',
        description: '',
        payment_method: PM.PERSONAL,
        reimbursement_status: RS.PENDING,
      })

      // Call success callback
      if (onSuccess) {
        onSuccess()
      }
    } catch (err: any) {
      console.error('Failed to create transaction:', err)
      setError(err.response?.data?.detail || 'Failed to create expense')
    } finally {
      setIsLoading(false)
    }
  }

  const updateField = (field: keyof TransactionCreate, value: any) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }))
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Add Expense</h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Date */}
        <div>
          <label htmlFor="transaction_date" className="block text-sm font-medium text-gray-700 mb-1">
            Date *
          </label>
          <input
            id="transaction_date"
            type="date"
            value={formData.transaction_date}
            onChange={(e) => updateField('transaction_date', e.target.value)}
            required
            disabled={isLoading}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
          />
        </div>

        {/* Amount */}
        <div>
          <label htmlFor="amount" className="block text-sm font-medium text-gray-700 mb-1">
            Amount * ($)
          </label>
          <input
            id="amount"
            type="number"
            step="0.01"
            min="0.01"
            value={formData.amount || ''}
            onChange={(e) => updateField('amount', parseFloat(e.target.value) || 0)}
            required
            disabled={isLoading}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            placeholder="0.00"
          />
        </div>

        {/* Family Member */}
        <div>
          <label htmlFor="family_member_id" className="block text-sm font-medium text-gray-700 mb-1">
            Family Member *
          </label>
          <select
            id="family_member_id"
            value={formData.family_member_id}
            onChange={(e) => updateField('family_member_id', e.target.value)}
            required
            disabled={isLoading}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
          >
            <option value="">Select a family member</option>
            {familyMembers.map((member) => (
              <option key={member.id} value={member.id}>
                {member.name} ({member.relationship})
              </option>
            ))}
          </select>
        </div>

        {/* Category */}
        <div>
          <label htmlFor="category_id" className="block text-sm font-medium text-gray-700 mb-1">
            Category *
          </label>
          <select
            id="category_id"
            value={formData.category_id}
            onChange={(e) => updateField('category_id', e.target.value)}
            required
            disabled={isLoading}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
          >
            <option value="">Select a category</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name} {category.is_hsa_eligible ? '(HSA Eligible)' : ''}
              </option>
            ))}
          </select>
        </div>

        {/* Merchant */}
        <div>
          <label htmlFor="merchant_name" className="block text-sm font-medium text-gray-700 mb-1">
            Merchant/Provider
          </label>
          <input
            id="merchant_name"
            type="text"
            value={formData.merchant_name || ''}
            onChange={(e) => updateField('merchant_name', e.target.value)}
            disabled={isLoading}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            placeholder="e.g., CVS Pharmacy, Dr. Smith"
          />
        </div>

        {/* Description */}
        <div>
          <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-1">
            Description
          </label>
          <textarea
            id="description"
            value={formData.description || ''}
            onChange={(e) => updateField('description', e.target.value)}
            disabled={isLoading}
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            placeholder="Additional notes about this expense"
          />
        </div>

        {/* Payment Method */}
        <div>
          <label htmlFor="payment_method" className="block text-sm font-medium text-gray-700 mb-1">
            Payment Method *
          </label>
          <select
            id="payment_method"
            value={formData.payment_method}
            onChange={(e) => updateField('payment_method', e.target.value as PaymentMethod)}
            required
            disabled={isLoading}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
          >
            {Object.values(PM).map((method) => (
              <option key={method} value={method}>
                {getPaymentMethodLabel(method)}
              </option>
            ))}
          </select>
        </div>

        {/* Reimbursement Status */}
        <div>
          <label htmlFor="reimbursement_status" className="block text-sm font-medium text-gray-700 mb-1">
            Reimbursement Status *
          </label>
          <select
            id="reimbursement_status"
            value={formData.reimbursement_status}
            onChange={(e) => updateField('reimbursement_status', e.target.value as ReimbursementStatus)}
            required
            disabled={isLoading}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
          >
            {Object.values(RS).map((status) => (
              <option key={status} value={status}>
                {getReimbursementStatusLabel(status)}
              </option>
            ))}
          </select>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        {/* Buttons */}
        <div className="flex gap-3 pt-4">
          <button
            type="submit"
            disabled={isLoading}
            className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-medium py-2 px-4 rounded-lg transition-colors"
          >
            {isLoading ? 'Saving...' : 'Add Expense'}
          </button>
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              disabled={isLoading}
              className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              Cancel
            </button>
          )}
        </div>
      </form>
    </div>
  )
}
