import { Link } from 'react-router-dom'

export default function Dashboard() {
  return (
    <div className="container mx-auto px-4 py-8">
      <header className="mb-8">
        <h1 className="text-4xl font-bold text-gray-900 mb-2">HSA Tracker</h1>
        <p className="text-gray-600">Welcome to your self-hosted HSA expense tracker</p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        {/* Dashboard Cards */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500 mb-2">Current Balance</h3>
          <p className="text-3xl font-bold text-gray-900">$0.00</p>
          <p className="text-sm text-gray-500 mt-2">No HSA account connected</p>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500 mb-2">YTD Spending</h3>
          <p className="text-3xl font-bold text-gray-900">$0.00</p>
          <p className="text-sm text-gray-500 mt-2">No transactions recorded</p>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500 mb-2">Pending Reimbursements</h3>
          <p className="text-3xl font-bold text-gray-900">$0.00</p>
          <p className="text-sm text-gray-500 mt-2">All caught up!</p>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">Getting Started</h2>
        <div className="space-y-4">
          <div className="flex items-start">
            <div className="flex-shrink-0 h-6 w-6 rounded-full bg-blue-500 text-white flex items-center justify-center text-sm font-medium">
              1
            </div>
            <div className="ml-4">
              <h3 className="text-lg font-medium text-gray-900">Set up your family</h3>
              <p className="text-gray-600">Add family members and configure tax dependent status</p>
            </div>
          </div>

          <div className="flex items-start">
            <div className="flex-shrink-0 h-6 w-6 rounded-full bg-blue-500 text-white flex items-center justify-center text-sm font-medium">
              2
            </div>
            <div className="ml-4">
              <h3 className="text-lg font-medium text-gray-900">Configure AWS S3</h3>
              <p className="text-gray-600">
                Run <code className="bg-gray-100 px-2 py-1 rounded">terraform apply</code> in the terraform directory
              </p>
            </div>
          </div>

          <div className="flex items-start">
            <div className="flex-shrink-0 h-6 w-6 rounded-full bg-blue-500 text-white flex items-center justify-center text-sm font-medium">
              3
            </div>
            <div className="ml-4">
              <h3 className="text-lg font-medium text-gray-900">Add your first transaction</h3>
              <p className="text-gray-600">
                <Link to="/transactions" className="text-blue-600 hover:text-blue-800">
                  Start tracking expenses →
                </Link>
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-8 text-center text-sm text-gray-500">
        <p>
          HSA Tracker v0.1.0 • Self-hosted HSA expense tracking for families
        </p>
      </div>
    </div>
  )
}
