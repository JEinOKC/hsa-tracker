import { render, screen, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import UpdatePrompt from '../UpdatePrompt'

const mockUpdateServiceWorker = vi.fn()

vi.mock('virtual:pwa-register/react', () => ({
  useRegisterSW: vi.fn(),
}))

import { useRegisterSW } from 'virtual:pwa-register/react'
const mockUseRegisterSW = vi.mocked(useRegisterSW)

beforeEach(() => {
  vi.clearAllMocks()
})

describe('UpdatePrompt', () => {
  it('renders nothing when no update is available', () => {
    mockUseRegisterSW.mockReturnValue({
      needRefresh: [false, vi.fn()],
      offlineReady: [false, vi.fn()],
      updateServiceWorker: mockUpdateServiceWorker,
    })
    const { container } = render(<UpdatePrompt />)
    expect(container.firstChild).toBeNull()
  })

  it('renders the banner when an update is available', () => {
    mockUseRegisterSW.mockReturnValue({
      needRefresh: [true, vi.fn()],
      offlineReady: [false, vi.fn()],
      updateServiceWorker: mockUpdateServiceWorker,
    })
    render(<UpdatePrompt />)
    expect(screen.getByText('A new version is available.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reload' })).toBeInTheDocument()
  })

  it('calls updateServiceWorker(true) when Reload is clicked', () => {
    mockUseRegisterSW.mockReturnValue({
      needRefresh: [true, vi.fn()],
      offlineReady: [false, vi.fn()],
      updateServiceWorker: mockUpdateServiceWorker,
    })
    render(<UpdatePrompt />)
    fireEvent.click(screen.getByRole('button', { name: 'Reload' }))
    expect(mockUpdateServiceWorker).toHaveBeenCalledWith(true)
  })
})
