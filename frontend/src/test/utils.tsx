import { type ReactElement } from 'react'
import { render, type RenderOptions } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
}

function AllProviders({ children, initialEntries }: { children: React.ReactNode; initialEntries?: string[] }) {
  const queryClient = createTestQueryClient()
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>
    </QueryClientProvider>
  )
}

function renderWithProviders(
  ui: ReactElement,
  { initialEntries, ...options }: Omit<RenderOptions, 'wrapper'> & { initialEntries?: string[] } = {}
) {
  return render(ui, {
    wrapper: ({ children }) => <AllProviders initialEntries={initialEntries}>{children}</AllProviders>,
    ...options,
  })
}

export * from '@testing-library/react'
export { renderWithProviders as render }
