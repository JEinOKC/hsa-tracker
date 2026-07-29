import { render, screen, fireEvent, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ToastProvider, useToast } from '../Toast'

function ToastTrigger({ message, type }: { message: string; type?: 'success' | 'error' }) {
  const { toast } = useToast()
  return <button onClick={() => toast(message, type)}>Show Toast</button>
}

function renderWithProvider(message = 'Hello toast', type?: 'success' | 'error') {
  return render(
    <ToastProvider>
      <ToastTrigger message={message} type={type} />
    </ToastProvider>
  )
}

describe('Toast', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('shows a toast when triggered', () => {
    renderWithProvider('Sync complete')
    fireEvent.click(screen.getByText('Show Toast'))
    expect(screen.getByRole('alert')).toHaveTextContent('Sync complete')
  })

  it('dismisses automatically after 6 seconds', () => {
    renderWithProvider('Auto dismiss')
    fireEvent.click(screen.getByText('Show Toast'))
    expect(screen.getByRole('alert')).toBeInTheDocument()
    act(() => vi.advanceTimersByTime(6000))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('can be manually dismissed', () => {
    renderWithProvider('Manual dismiss')
    fireEvent.click(screen.getByText('Show Toast'))
    fireEvent.click(screen.getByLabelText('Dismiss'))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('applies error styling for error type', () => {
    renderWithProvider('Something went wrong', 'error')
    fireEvent.click(screen.getByText('Show Toast'))
    expect(screen.getByRole('alert')).toHaveClass('bg-red-600')
  })

  it('applies default dark styling for success type', () => {
    renderWithProvider('All good', 'success')
    fireEvent.click(screen.getByText('Show Toast'))
    expect(screen.getByRole('alert')).toHaveClass('bg-gray-900')
  })

  it('stacks multiple toasts', () => {
    renderWithProvider('First')
    const button = screen.getByText('Show Toast')
    fireEvent.click(button)
    fireEvent.click(button)
    expect(screen.getAllByRole('alert')).toHaveLength(2)
  })

  it('anchors to the bottom so it never covers the header refresh button', () => {
    renderWithProvider('Placement test')
    const region = screen.getByRole('region', { name: 'Notifications' })

    // Must not be pinned to the top, where it overlapped the header controls.
    expect(region.style.top).toBe('')
    expect(region.className).not.toMatch(/(^|\s)top-/)
    expect(region.className).toMatch(/(^|\s)bottom-\[/)
  })

  it('clears the mobile tab bar and accounts for iOS safe area inset', () => {
    renderWithProvider('Safe area test')
    const region = screen.getByRole('region', { name: 'Notifications' })

    // Mobile: offset by the tab bar height plus the home-indicator inset.
    expect(region.className).toContain(
      'bottom-[calc(4.25rem+max(env(safe-area-inset-bottom),0.75rem))]'
    )
    // md+: tab bar is hidden, so it drops to the bottom edge.
    expect(region.className).toContain(
      'md:bottom-[calc(1rem+env(safe-area-inset-bottom,0px))]'
    )
  })
})
