import { useState } from 'react'
import { Link } from 'react-router-dom'
import LoginForm from '../components/auth/LoginForm'

export default function Login() {
  const [showRegister, setShowRegister] = useState(false)

  if (showRegister) {
    // Redirect to register page
    window.location.href = '/register'
    return null
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="max-w-md w-full">
        <div className="bg-white rounded-lg shadow-lg p-8">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">HSA Tracker</h1>
            <p className="text-gray-600">Sign in to your account</p>
          </div>

          <LoginForm />

          <div className="mt-6 text-center">
            <p className="text-sm text-gray-600">
              Don't have an account?{' '}
              <Link to="/register" className="text-blue-600 hover:text-blue-800 font-medium">
                Create one
              </Link>
            </p>
          </div>

          <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h3 className="text-sm font-medium text-blue-900 mb-1">✨ Auth is Now Working!</h3>
            <p className="text-sm text-blue-700">
              Create an account to get started. Email/password and TOTP 2FA are fully functional!
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
