/**
 * Transactions page tests - documents current placeholder state.
 * Update these tests when real transaction management is implemented.
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '../../test/utils'
import Transactions from '../Transactions'

describe('Transactions (placeholder)', () => {
  it('renders page title', () => {
    render(<Transactions />)
    expect(screen.getByText('Transactions')).toBeInTheDocument()
  })

  it('shows empty state message', () => {
    render(<Transactions />)
    expect(screen.getByText('No transactions')).toBeInTheDocument()
    expect(screen.getByText(/get started by adding your first expense/i)).toBeInTheDocument()
  })

  it('has Add Transaction buttons', () => {
    render(<Transactions />)
    const buttons = screen.getAllByText('Add Transaction')
    expect(buttons.length).toBeGreaterThanOrEqual(1)
  })

  it('has back to dashboard link', () => {
    render(<Transactions />)
    const link = screen.getByText(/back to dashboard/i)
    expect(link).toHaveAttribute('href', '/')
  })

  it('shows receipt format tip', () => {
    render(<Transactions />)
    expect(screen.getByText(/jpeg, png, heic, and pdf/i)).toBeInTheDocument()
  })
})
