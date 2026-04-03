import { describe, it, expect, vi, beforeEach } from 'vitest'
import userEvent from '@testing-library/user-event'
import { render, screen, waitFor } from '../../../test/utils'
import PasskeyRegisterForm from '../PasskeyRegisterForm'

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

// vi.mock factories are hoisted, so declare shared mocks with vi.hoisted
const { mockGetAppConfig } = vi.hoisted(() => ({
  mockGetAppConfig: vi.fn(),
}))

vi.mock('../../../services/passkey', () => ({
  default: {
    isSupported: vi.fn(() => true),
    getAppConfig: mockGetAppConfig,
    register: vi.fn(),
    login: vi.fn(),
  },
}))

vi.mock('../../../services/auth', () => ({
  default: {
    isAuthenticated: vi.fn(() => false),
  },
}))

import passkeyService from '../../../services/passkey'

describe('PasskeyRegisterForm', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(passkeyService.isSupported as any).mockReturnValue(true)
    // Default: open registration (no invite required)
    mockGetAppConfig.mockResolvedValue({ require_invite: false })
  })

  it('renders username, display name, and device name inputs', async () => {
    render(<PasskeyRegisterForm />)
    await waitFor(() => expect(mockGetAppConfig).toHaveBeenCalled())
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/full name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/device name/i)).toBeInTheDocument()
  })

  it('renders submit button', async () => {
    render(<PasskeyRegisterForm />)
    await waitFor(() => expect(mockGetAppConfig).toHaveBeenCalled())
    expect(screen.getByRole('button', { name: /create account with passkey/i })).toBeInTheDocument()
  })

  it('does not show invite token field when require_invite is false', async () => {
    render(<PasskeyRegisterForm />)
    await waitFor(() => expect(mockGetAppConfig).toHaveBeenCalled())
    expect(screen.queryByLabelText(/invite token/i)).not.toBeInTheDocument()
  })

  it('shows invite token field when require_invite is true', async () => {
    mockGetAppConfig.mockResolvedValue({ require_invite: true })
    render(<PasskeyRegisterForm />)
    await waitFor(() => {
      expect(screen.getByLabelText(/invite token/i)).toBeInTheDocument()
    })
  })

  it('converts username to lowercase and strips invalid chars', async () => {
    const user = userEvent.setup()
    render(<PasskeyRegisterForm />)
    await waitFor(() => expect(mockGetAppConfig).toHaveBeenCalled())
    const input = screen.getByLabelText(/username/i)
    await user.type(input, 'Test.User!')
    expect(input).toHaveValue('testuser')
  })

  it('calls register then login on submit without invite token', async () => {
    const user = userEvent.setup()
    ;(passkeyService.register as any).mockResolvedValue({ id: '1', username: 'newuser' })
    ;(passkeyService.login as any).mockResolvedValue({ access_token: 'at' })

    render(<PasskeyRegisterForm />)
    await waitFor(() => expect(mockGetAppConfig).toHaveBeenCalled())
    await user.type(screen.getByLabelText(/username/i), 'newuser')
    await user.type(screen.getByLabelText(/full name/i), 'New User')
    await user.click(screen.getByRole('button', { name: /create account with passkey/i }))

    await waitFor(() => {
      expect(passkeyService.register).toHaveBeenCalledWith('newuser', 'New User', undefined, undefined, undefined)
    })
    await waitFor(() => {
      expect(passkeyService.login).toHaveBeenCalledWith('newuser')
    })
  })

  it('passes invite token to register when require_invite is true', async () => {
    mockGetAppConfig.mockResolvedValue({ require_invite: true })
    ;(passkeyService.register as any).mockResolvedValue({ id: '1', username: 'inviteduser' })
    ;(passkeyService.login as any).mockResolvedValue({ access_token: 'at' })

    const user = userEvent.setup()
    render(<PasskeyRegisterForm />)
    await waitFor(() => screen.getByLabelText(/invite token/i))

    await user.type(screen.getByLabelText(/invite token/i), 'brave-silent-wolf')
    await user.type(screen.getByLabelText(/username/i), 'inviteduser')
    await user.type(screen.getByLabelText(/full name/i), 'Invited User')
    await user.click(screen.getByRole('button', { name: /create account with passkey/i }))

    await waitFor(() => {
      expect(passkeyService.register).toHaveBeenCalledWith(
        'inviteduser', 'Invited User', undefined, 'brave-silent-wolf', undefined
      )
    })
  })

  it('pre-fills invite token from prop (read-only) and does not fetch config', async () => {
    render(<PasskeyRegisterForm inviteToken="pre-filled-token" />)
    const tokenInput = screen.getByLabelText(/invite token/i)
    expect(tokenInput).toHaveValue('pre-filled-token')
    expect(tokenInput).toHaveAttribute('readonly')
    expect(mockGetAppConfig).not.toHaveBeenCalled()
  })

  it('shows family PIN field when requirePin prop is true', () => {
    render(<PasskeyRegisterForm inviteToken="tok" requirePin={true} />)
    expect(screen.getByLabelText(/family pin/i)).toBeInTheDocument()
  })

  it('does not show family PIN field when requirePin is false', () => {
    render(<PasskeyRegisterForm inviteToken="tok" requirePin={false} />)
    expect(screen.queryByLabelText(/family pin/i)).not.toBeInTheDocument()
  })

  it('passes family PIN to register call', async () => {
    ;(passkeyService.register as any).mockResolvedValue({ id: '1', username: 'pinuser' })
    ;(passkeyService.login as any).mockResolvedValue({ access_token: 'at' })

    const user = userEvent.setup()
    render(<PasskeyRegisterForm inviteToken="fixed-token" requirePin={true} />)

    await user.type(screen.getByLabelText(/family pin/i), 'silent-falcon')
    await user.type(screen.getByLabelText(/username/i), 'pinuser')
    await user.type(screen.getByLabelText(/full name/i), 'Pin User')
    await user.click(screen.getByRole('button', { name: /create account with passkey/i }))

    await waitFor(() => {
      expect(passkeyService.register).toHaveBeenCalledWith(
        'pinuser', 'Pin User', undefined, 'fixed-token', 'silent-falcon'
      )
    })
  })

  it('shows error when passkeys not supported', async () => {
    const user = userEvent.setup()
    ;(passkeyService.isSupported as any).mockReturnValue(false)
    render(<PasskeyRegisterForm />)
    await waitFor(() => expect(mockGetAppConfig).toHaveBeenCalled())
    await user.type(screen.getByLabelText(/username/i), 'newuser')
    await user.type(screen.getByLabelText(/full name/i), 'New User')
    await user.click(screen.getByRole('button', { name: /create account with passkey/i }))
    await waitFor(() => {
      expect(screen.getByText(/not supported/i)).toBeInTheDocument()
    })
  })

  it('shows error on registration failure', async () => {
    const user = userEvent.setup()
    ;(passkeyService.register as any).mockRejectedValue(new Error('Registration failed'))
    render(<PasskeyRegisterForm />)
    await waitFor(() => expect(mockGetAppConfig).toHaveBeenCalled())
    await user.type(screen.getByLabelText(/username/i), 'newuser')
    await user.type(screen.getByLabelText(/full name/i), 'New User')
    await user.click(screen.getByRole('button', { name: /create account with passkey/i }))
    await waitFor(() => {
      expect(screen.getByText(/registration failed/i)).toBeInTheDocument()
    })
  })

  it('shows Creating account state while loading', async () => {
    const user = userEvent.setup()
    ;(passkeyService.register as any).mockImplementation(() => new Promise(() => {}))
    render(<PasskeyRegisterForm />)
    await waitFor(() => expect(mockGetAppConfig).toHaveBeenCalled())
    await user.type(screen.getByLabelText(/username/i), 'newuser')
    await user.type(screen.getByLabelText(/full name/i), 'New User')
    await user.click(screen.getByRole('button', { name: /create account with passkey/i }))
    await waitFor(() => {
      expect(screen.getByText(/creating account/i)).toBeInTheDocument()
    })
  })

  it('falls back to open registration if config fetch fails', async () => {
    mockGetAppConfig.mockRejectedValue(new Error('network error'))
    render(<PasskeyRegisterForm />)
    // Should not show invite field even after the rejection settles
    await waitFor(() => expect(mockGetAppConfig).toHaveBeenCalled())
    expect(screen.queryByLabelText(/invite token/i)).not.toBeInTheDocument()
  })
})
