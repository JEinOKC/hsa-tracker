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

vi.mock('../../../services/passkey', () => ({
  default: {
    isSupported: vi.fn(() => true),
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
  })

  it('renders username, display name, and device name inputs', () => {
    render(<PasskeyRegisterForm />)
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/full name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/device name/i)).toBeInTheDocument()
  })

  it('renders submit button', () => {
    render(<PasskeyRegisterForm />)
    expect(screen.getByRole('button', { name: /create account with passkey/i })).toBeInTheDocument()
  })

  it('converts username to lowercase and strips invalid chars', async () => {
    const user = userEvent.setup()
    render(<PasskeyRegisterForm />)
    const input = screen.getByLabelText(/username/i)
    await user.type(input, 'Test.User!')
    // Should strip . and !, lowercase T
    expect(input).toHaveValue('testuser')
  })

  it('calls register then login on submit', async () => {
    const user = userEvent.setup()
    ;(passkeyService.register as any).mockResolvedValue({ id: '1', username: 'newuser' })
    ;(passkeyService.login as any).mockResolvedValue({ access_token: 'at' })

    render(<PasskeyRegisterForm />)
    await user.type(screen.getByLabelText(/username/i), 'newuser')
    await user.type(screen.getByLabelText(/full name/i), 'New User')
    await user.click(screen.getByRole('button', { name: /create account with passkey/i }))

    await waitFor(() => {
      expect(passkeyService.register).toHaveBeenCalledWith('newuser', 'New User', undefined)
    })
    await waitFor(() => {
      expect(passkeyService.login).toHaveBeenCalledWith('newuser')
    })
  })

  it('shows error when passkeys not supported', async () => {
    const user = userEvent.setup()
    ;(passkeyService.isSupported as any).mockReturnValue(false)
    render(<PasskeyRegisterForm />)
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
    await user.type(screen.getByLabelText(/username/i), 'newuser')
    await user.type(screen.getByLabelText(/full name/i), 'New User')
    await user.click(screen.getByRole('button', { name: /create account with passkey/i }))
    await waitFor(() => {
      expect(screen.getByText(/creating account/i)).toBeInTheDocument()
    })
  })
})
