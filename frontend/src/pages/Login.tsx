import { Link } from 'react-router-dom'
import PasskeyLoginForm from '../components/auth/PasskeyLoginForm'

export default function Login() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="max-w-md w-full">
        <div className="bg-white rounded-lg shadow-lg p-8">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">HSA Tracker</h1>
            <p className="text-gray-600">Secure, passwordless login</p>
          </div>

          <PasskeyLoginForm />

          <div className="mt-6 text-center">
            <p className="text-sm text-gray-600">
              Don't have an account?{' '}
              <Link to="/register" className="text-sky-600 hover:text-sky-800 font-medium">
                Create one
              </Link>
            </p>
          </div>

          <div className="mt-6 bg-green-50 border border-green-200 rounded-lg p-4">
            <h3 className="text-sm font-medium text-green-900 mb-1">🔐 Passkey Authentication!</h3>
            <p className="text-sm text-green-700">
              No email or password required. Login securely with your device's biometric authentication!
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
