import type { Config } from 'tailwindcss'

export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Custom theme colors (can be overridden by users)
        primary: 'var(--color-primary, #3b82f6)',
        secondary: 'var(--color-secondary, #64748b)',
        success: 'var(--color-success, #10b981)',
        warning: 'var(--color-warning, #f59e0b)',
        danger: 'var(--color-danger, #ef4444)',
      },
    },
  },
  plugins: [],
} satisfies Config
