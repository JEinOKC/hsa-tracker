import '@testing-library/jest-dom'

// Mock window.PublicKeyCredential for WebAuthn tests
Object.defineProperty(window, 'PublicKeyCredential', {
  value: class MockPublicKeyCredential {},
  writable: true,
  configurable: true,
})
