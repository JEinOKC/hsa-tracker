import { render, screen, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import UpdatePrompt from '../UpdatePrompt'

vi.mock('../../hooks/useAppUpdate', () => ({
  useAppUpdate: vi.fn(),
}))

import { useAppUpdate } from '../../hooks/useAppUpdate'
const mockUseAppUpdate = vi.mocked(useAppUpdate)
const mockApplyUpdate = vi.fn()

function mockState(needRefresh: boolean) {
  mockUseAppUpdate.mockReturnValue({
    needRefresh,
    checkStatus: 'idle',
    checkForUpdate: vi.fn(),
    applyUpdate: mockApplyUpdate,
  })
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('UpdatePrompt', () => {
  it('renders nothing when no update is available', () => {
    mockState(false)
    const { container } = render(<UpdatePrompt />)
    expect(container.firstChild).toBeNull()
  })

  it('renders the banner when an update is available', () => {
    mockState(true)
    render(<UpdatePrompt />)
    expect(screen.getByText('A new version is available.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reload' })).toBeInTheDocument()
  })

  it('applies the update when Reload is clicked', () => {
    mockState(true)
    render(<UpdatePrompt />)
    fireEvent.click(screen.getByRole('button', { name: 'Reload' }))
    expect(mockApplyUpdate).toHaveBeenCalled()
  })
})
