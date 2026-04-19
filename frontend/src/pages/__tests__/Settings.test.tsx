import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '../../test/utils'
import Settings from '../Settings'

vi.mock('../../services/household', () => ({
  householdService: {
    getMine: vi.fn(),
    updateSettings: vi.fn(),
  },
}))

vi.mock('../../services/pushNotifications', () => ({
  isPushSupported: vi.fn(),
  getExistingSubscription: vi.fn(),
  subscribeToPush: vi.fn(),
  saveSubscription: vi.fn(),
  removeSubscription: vi.fn(),
}))

vi.mock('../../services/periodicSync', () => ({
  registerPeriodicSync: vi.fn(),
}))

import {
  isPushSupported,
  getExistingSubscription,
  subscribeToPush,
  saveSubscription,
  removeSubscription,
} from '../../services/pushNotifications'
import { registerPeriodicSync } from '../../services/periodicSync'
import { householdService } from '../../services/household'

const mockGetMine = vi.mocked(householdService.getMine)
const mockUpdateSettings = vi.mocked(householdService.updateSettings)
const mockIsPushSupported = vi.mocked(isPushSupported)
const mockGetExisting = vi.mocked(getExistingSubscription)
const mockSubscribeToPush = vi.mocked(subscribeToPush)
const mockSaveSubscription = vi.mocked(saveSubscription)
const mockRemoveSubscription = vi.mocked(removeSubscription)
const mockRegisterPeriodicSync = vi.mocked(registerPeriodicSync)

const mockSub = {
  endpoint: 'https://push.example.com/sub/1',
  toJSON: () => ({ endpoint: 'https://push.example.com/sub/1', keys: { p256dh: 'key', auth: 'auth' } }),
  unsubscribe: vi.fn().mockResolvedValue(true),
} as unknown as PushSubscription

const mockAdminHousehold = {
  id: 'hh-1',
  name: 'Test Household',
  created_by_id: 'user-1',
  strict_eligibility: true,
  is_admin: true,
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.removeItem('hsa_sync_interval_ms')
  mockGetMine.mockResolvedValue(null)
  mockRegisterPeriodicSync.mockResolvedValue(undefined)
  // Default: supported, no existing subscription
  mockIsPushSupported.mockReturnValue(true)
  mockGetExisting.mockResolvedValue(null)
  Object.defineProperty(window, 'Notification', {
    value: { permission: 'default' },
    writable: true,
    configurable: true,
  })
})

describe('Settings page', () => {
  it('renders Push Notifications heading', async () => {
    render(<Settings />)
    expect(screen.getByText('Push Notifications')).toBeInTheDocument()
  })

  it('shows unsupported message when push is not supported', async () => {
    mockIsPushSupported.mockReturnValue(false)
    render(<Settings />)
    expect(screen.getByText(/not supported/i)).toBeInTheDocument()
  })

  it('shows denied message when permission was denied', async () => {
    Object.defineProperty(window, 'Notification', {
      value: { permission: 'denied' },
      writable: true,
      configurable: true,
    })
    render(<Settings />)
    expect(screen.getByText(/permission was denied/i)).toBeInTheDocument()
  })

  it('shows Enable button when not subscribed', async () => {
    render(<Settings />)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /enable push notifications/i })).toBeInTheDocument()
    })
  })

  it('shows subscribed status when existing subscription is found', async () => {
    mockGetExisting.mockResolvedValue(mockSub)
    render(<Settings />)
    await waitFor(() => {
      expect(screen.getByText(/subscribed/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /disable/i })).toBeInTheDocument()
    })
  })

  it('clicking Enable calls subscribeToPush then saveSubscription', async () => {
    mockSubscribeToPush.mockResolvedValue(mockSub)
    mockSaveSubscription.mockResolvedValue(undefined)

    render(<Settings />)
    await waitFor(() => screen.getByRole('button', { name: /enable push notifications/i }))
    fireEvent.click(screen.getByRole('button', { name: /enable push notifications/i }))

    await waitFor(() => {
      expect(mockSubscribeToPush).toHaveBeenCalled()
      expect(mockSaveSubscription).toHaveBeenCalledWith(mockSub)
    })
  })

  it('shows subscribed status after enabling', async () => {
    mockSubscribeToPush.mockResolvedValue(mockSub)
    mockSaveSubscription.mockResolvedValue(undefined)

    render(<Settings />)
    await waitFor(() => screen.getByRole('button', { name: /enable push notifications/i }))
    fireEvent.click(screen.getByRole('button', { name: /enable push notifications/i }))

    await waitFor(() => {
      expect(screen.getByText(/subscribed/i)).toBeInTheDocument()
    })
  })

  it('shows denied state when subscribeToPush returns null due to denied permission', async () => {
    // Start with 'default' so the Enable button renders, then flip to 'denied'
    // so handleEnable's post-subscribe check sees the denied state.
    const notif = { permission: 'default' as NotificationPermission }
    Object.defineProperty(window, 'Notification', { get: () => notif, configurable: true })

    mockSubscribeToPush.mockImplementation(async () => {
      notif.permission = 'denied'
      return null
    })

    render(<Settings />)
    await waitFor(() => screen.getByRole('button', { name: /enable push notifications/i }))
    fireEvent.click(screen.getByRole('button', { name: /enable push notifications/i }))

    await waitFor(() => {
      expect(screen.getByText(/permission was denied/i)).toBeInTheDocument()
    })
  })

  it('clicking Disable calls removeSubscription', async () => {
    mockGetExisting.mockResolvedValue(mockSub)
    mockRemoveSubscription.mockResolvedValue(undefined)

    render(<Settings />)
    await waitFor(() => screen.getByRole('button', { name: /disable/i }))
    fireEvent.click(screen.getByRole('button', { name: /disable/i }))

    await waitFor(() => {
      expect(mockRemoveSubscription).toHaveBeenCalledWith(mockSub)
    })
  })

  it('shows Enable button again after disabling', async () => {
    mockGetExisting.mockResolvedValue(mockSub)
    mockRemoveSubscription.mockResolvedValue(undefined)

    render(<Settings />)
    await waitFor(() => screen.getByRole('button', { name: /disable/i }))
    fireEvent.click(screen.getByRole('button', { name: /disable/i }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /enable push notifications/i })).toBeInTheDocument()
    })
  })
})

describe('Calculation Settings section', () => {
  it('shows Calculation Settings section when user is admin', async () => {
    mockGetMine.mockResolvedValue(mockAdminHousehold)
    render(<Settings />)
    await waitFor(() => {
      expect(screen.getByText('Calculation Settings')).toBeInTheDocument()
    })
  })

  it('does not show Calculation Settings section when user is not admin', async () => {
    mockGetMine.mockResolvedValue({ ...mockAdminHousehold, is_admin: false })
    render(<Settings />)
    await waitFor(() => screen.getByText('Push Notifications'))
    expect(screen.queryByText('Calculation Settings')).not.toBeInTheDocument()
  })

  it('does not show Calculation Settings section when no household', async () => {
    mockGetMine.mockResolvedValue(null)
    render(<Settings />)
    await waitFor(() => screen.getByText('Push Notifications'))
    expect(screen.queryByText('Calculation Settings')).not.toBeInTheDocument()
  })

  it('toggle reflects strict_eligibility state (on)', async () => {
    mockGetMine.mockResolvedValue({ ...mockAdminHousehold, strict_eligibility: true })
    render(<Settings />)
    await waitFor(() => {
      expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true')
    })
  })

  it('toggle reflects strict_eligibility state (off)', async () => {
    mockGetMine.mockResolvedValue({ ...mockAdminHousehold, strict_eligibility: false })
    render(<Settings />)
    await waitFor(() => {
      expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'false')
    })
  })

  it('clicking toggle calls updateSettings with toggled value', async () => {
    mockGetMine.mockResolvedValue({ ...mockAdminHousehold, strict_eligibility: true })
    mockUpdateSettings.mockResolvedValue({ ...mockAdminHousehold, strict_eligibility: false })
    render(<Settings />)
    await waitFor(() => screen.getByRole('switch'))
    fireEvent.click(screen.getByRole('switch'))
    await waitFor(() => {
      expect(mockUpdateSettings).toHaveBeenCalledWith(false)
    })
  })

  it('toggle updates to off after successful updateSettings', async () => {
    mockGetMine.mockResolvedValue({ ...mockAdminHousehold, strict_eligibility: true })
    mockUpdateSettings.mockResolvedValue({ ...mockAdminHousehold, strict_eligibility: false })
    render(<Settings />)
    await waitFor(() => screen.getByRole('switch'))
    fireEvent.click(screen.getByRole('switch'))
    await waitFor(() => {
      expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'false')
    })
  })
})

describe('Sync Interval section', () => {
  it('renders the Sync Interval heading', async () => {
    render(<Settings />)
    expect(screen.getByText('Sync Interval')).toBeInTheDocument()
  })

  it('defaults to 24h when no localStorage value', async () => {
    render(<Settings />)
    const select = screen.getByRole('combobox') as HTMLSelectElement
    expect(select.value).toBe(String(24 * 60 * 60 * 1000))
  })

  it('reads stored interval from localStorage on mount', async () => {
    const fourHoursMs = 4 * 60 * 60 * 1000
    localStorage.setItem('hsa_sync_interval_ms', String(fourHoursMs))
    render(<Settings />)
    const select = screen.getByRole('combobox') as HTMLSelectElement
    expect(select.value).toBe(String(fourHoursMs))
  })

  it('writes new value to localStorage when interval changes', async () => {
    render(<Settings />)
    const select = screen.getByRole('combobox')
    fireEvent.change(select, { target: { value: String(8 * 60 * 60 * 1000) } })
    expect(localStorage.getItem('hsa_sync_interval_ms')).toBe(String(8 * 60 * 60 * 1000))
  })

  it('calls registerPeriodicSync when interval changes', async () => {
    render(<Settings />)
    const select = screen.getByRole('combobox')
    const eightHoursMs = 8 * 60 * 60 * 1000
    fireEvent.change(select, { target: { value: String(eightHoursMs) } })
    expect(mockRegisterPeriodicSync).toHaveBeenCalledWith(eightHoursMs)
  })
})
