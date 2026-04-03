import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '../../test/utils'
import InvitePage from '../InvitePage'

// Mock useParams to supply a token
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useParams: () => ({ token: 'brave-silent-wolf' }) }
})

const { mockValidate } = vi.hoisted(() => ({ mockValidate: vi.fn() }))

vi.mock('../../services/familyInvites', () => ({
  default: { validate: mockValidate },
}))

// PasskeyRegisterForm is rendered when invite is valid — mock to avoid full form setup
vi.mock('../../components/auth/PasskeyRegisterForm', () => ({
  default: ({ inviteToken, requirePin }: { inviteToken?: string; requirePin?: boolean }) => (
    <div data-testid="register-form">
      <span data-testid="invite-token">{inviteToken}</span>
      <span data-testid="require-pin">{String(requirePin)}</span>
    </div>
  ),
}))

describe('InvitePage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows loading state initially', () => {
    mockValidate.mockReturnValue(new Promise(() => {})) // never resolves
    render(<InvitePage />)
    expect(screen.getByText(/checking invite link/i)).toBeInTheDocument()
  })

  it('shows error when token is invalid', async () => {
    mockValidate.mockResolvedValue({ valid: false, require_pin: false, expires_at: null })
    render(<InvitePage />)
    await waitFor(() => {
      expect(screen.getByText(/invalid or expired/i)).toBeInTheDocument()
    })
  })

  it('shows error when validate call fails', async () => {
    mockValidate.mockRejectedValue(new Error('network error'))
    render(<InvitePage />)
    await waitFor(() => {
      expect(screen.getByText(/invalid or expired/i)).toBeInTheDocument()
    })
  })

  it('renders registration form when token is valid', async () => {
    mockValidate.mockResolvedValue({ valid: true, require_pin: false, expires_at: '2026-04-01T00:00:00' })
    render(<InvitePage />)
    await waitFor(() => {
      expect(screen.getByTestId('register-form')).toBeInTheDocument()
    })
  })

  it('passes invite token to registration form', async () => {
    mockValidate.mockResolvedValue({ valid: true, require_pin: false, expires_at: '2026-04-01T00:00:00' })
    render(<InvitePage />)
    await waitFor(() => {
      expect(screen.getByTestId('invite-token')).toHaveTextContent('brave-silent-wolf')
    })
  })

  it('passes require_pin=true to registration form when needed', async () => {
    mockValidate.mockResolvedValue({ valid: true, require_pin: true, expires_at: '2026-04-01T00:00:00' })
    render(<InvitePage />)
    await waitFor(() => {
      expect(screen.getByTestId('require-pin')).toHaveTextContent('true')
    })
  })

  it('passes require_pin=false to registration form when not needed', async () => {
    mockValidate.mockResolvedValue({ valid: true, require_pin: false, expires_at: '2026-04-01T00:00:00' })
    render(<InvitePage />)
    await waitFor(() => {
      expect(screen.getByTestId('require-pin')).toHaveTextContent('false')
    })
  })
})
