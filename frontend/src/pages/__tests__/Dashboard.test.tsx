/**
 * Dashboard page tests - documents current placeholder state.
 * Update these tests when real data fetching is implemented.
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '../../test/utils'
import Dashboard from '../Dashboard'

describe('Dashboard (placeholder)', () => {
  it('renders page title', () => {
    render(<Dashboard />)
    expect(screen.getByText('HSA Tracker')).toBeInTheDocument()
  })

  it('shows three $0.00 dashboard cards', () => {
    render(<Dashboard />)
    const zeroes = screen.getAllByText('$0.00')
    expect(zeroes).toHaveLength(3)
  })

  it('shows Current Balance card', () => {
    render(<Dashboard />)
    expect(screen.getByText('Current Balance')).toBeInTheDocument()
    expect(screen.getByText('No HSA account connected')).toBeInTheDocument()
  })

  it('shows getting started steps', () => {
    render(<Dashboard />)
    expect(screen.getByText('Set up your family')).toBeInTheDocument()
    expect(screen.getByText('Configure AWS S3')).toBeInTheDocument()
    expect(screen.getByText('Add your first transaction')).toBeInTheDocument()
  })

  it('has link to transactions page', () => {
    render(<Dashboard />)
    const link = screen.getByText(/start tracking expenses/i)
    expect(link).toHaveAttribute('href', '/transactions')
  })
})
