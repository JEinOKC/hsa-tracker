import { describe, it, expect, vi, beforeEach } from 'vitest'
import userEvent from '@testing-library/user-event'
import { render, screen, waitFor } from '../../../test/utils'
import PasskeyLoginForm from '../PasskeyLoginForm'

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useLocation: () => ({ state: null, pathname: '/login' }),
  }
})

vi.mock('../../../services/passkey', () => ({
  default: {
    isSupported: vi.fn(() => true),
    login: vi.fn(),
  },
}))

// Also mock auth service (imported but not directly used in form)
vi.mock('../../../services/auth', () => ({
  default: {
    isAuthenticated: vi.fn(() => false),
  },
}))

import passkeyService from '../../../services/passkey'

describe('PasskeyLoginForm', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(passkeyService.isSupported as any).mockReturnValue(true)
  })

  it('renders username input and submit button', () => {
    render(<PasskeyLoginForm />)
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /login with passkey/i })).toBeInTheDocument()
  })

  it('shows passwordless login info', () => {
    render(<PasskeyLoginForm />)
    expect(screen.getByText(/passwordless login/i)).toBeInTheDocument()
  })

  it('converts username to lowercase on input', async () => {
    const user = userEvent.setup()
    render(<PasskeyLoginForm />)
    const input = screen.getByLabelText(/username/i)
    await user.type(input, 'TestUser')
    expect(input).toHaveValue('testuser')
  })

  it('calls passkeyService.login on submit', async () => {
    const user = userEvent.setup()
    ;(passkeyService.login as any).mockResolvedValue({})
    render(<PasskeyLoginForm />)
    await user.type(screen.getByLabelText(/username/i), 'testuser')
    await user.click(screen.getByRole('button', { name: /login with passkey/i }))
    await waitFor(() => {
      expect(passkeyService.login).toHaveBeenCalledWith('testuser')
    })
  })

  it('shows error when passkeys not supported', async () => {
    const user = userEvent.setup()
    ;(passkeyService.isSupported as any).mockReturnValue(false)
    render(<PasskeyLoginForm />)
    await user.type(screen.getByLabelText(/username/i), 'testuser')
    await user.click(screen.getByRole('button', { name: /login with passkey/i }))
    await waitFor(() => {
      expect(screen.getByText(/not supported/i)).toBeInTheDocument()
    })
  })

  it('shows error on login failure', async () => {
    const user = userEvent.setup()
    ;(passkeyService.login as any).mockRejectedValue(new Error('Auth failed'))
    render(<PasskeyLoginForm />)
    await user.type(screen.getByLabelText(/username/i), 'testuser')
    await user.click(screen.getByRole('button', { name: /login with passkey/i }))
    await waitFor(() => {
      expect(screen.getByText(/auth failed/i)).toBeInTheDocument()
    })
  })

  it('shows Authenticating state while loading', async () => {
    const user = userEvent.setup()
    // Login never resolves
    ;(passkeyService.login as any).mockImplementation(() => new Promise(() => {}))
    render(<PasskeyLoginForm />)
    await user.type(screen.getByLabelText(/username/i), 'testuser')
    await user.click(screen.getByRole('button', { name: /login with passkey/i }))
    await waitFor(() => {
      expect(screen.getByText(/authenticating/i)).toBeInTheDocument()
    })
  })
})
