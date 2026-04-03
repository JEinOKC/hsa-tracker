import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '../../test/utils'
import Settings from '../Settings'

vi.mock('../../services/pushNotifications', () => ({
  isPushSupported: vi.fn(),
  getExistingSubscription: vi.fn(),
  subscribeToPush: vi.fn(),
  saveSubscription: vi.fn(),
  removeSubscription: vi.fn(),
}))

import {
  isPushSupported,
  getExistingSubscription,
  subscribeToPush,
  saveSubscription,
  removeSubscription,
} from '../../services/pushNotifications'

const mockIsPushSupported = vi.mocked(isPushSupported)
const mockGetExisting = vi.mocked(getExistingSubscription)
const mockSubscribeToPush = vi.mocked(subscribeToPush)
const mockSaveSubscription = vi.mocked(saveSubscription)
const mockRemoveSubscription = vi.mocked(removeSubscription)

const mockSub = {
  endpoint: 'https://push.example.com/sub/1',
  toJSON: () => ({ endpoint: 'https://push.example.com/sub/1', keys: { p256dh: 'key', auth: 'auth' } }),
  unsubscribe: vi.fn().mockResolvedValue(true),
} as unknown as PushSubscription

beforeEach(() => {
  vi.clearAllMocks()
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
