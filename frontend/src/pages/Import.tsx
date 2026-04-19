import { useState, useRef } from 'react'
import { receiptsService, PharmacyImportResult } from '../services/receipts'

export default function Import() {
  return (
    <div className="max-w-2xl mx-auto px-4 py-6">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Import</h1>
      <p className="text-sm text-gray-500 mb-6">
        Import prescription history from your pharmacy to automatically match charges and mark HSA-eligible purchases.
      </p>

      <CvsPharmacyImport />

      <div className="mt-8 border-t border-gray-100 pt-6">
        <h2 className="text-base font-semibold text-gray-800 mb-1">Generic line items</h2>
        <p className="text-sm text-gray-500 mb-3">
          For Walgreens or other retailers, download the template below, fill it in from your receipt, and upload it on the individual transaction.
        </p>
        <a
          href="/api/v1/bank/imports/line-items-template.csv"
          download="line-items-template.csv"
          className="text-sm text-blue-600 hover:underline"
        >
          Download CSV template
        </a>
      </div>
    </div>
  )
}

function CvsPharmacyImport() {
  const [result, setResult] = useState<PharmacyImportResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = async (file: File) => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await receiptsService.importCvsPharmacy(file)
      setResult(data)
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Import failed. Please check the file and try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    // Reset so same file can be re-selected after an error
    e.target.value = ''
  }

  return (
    <div>
      <h2 className="text-base font-semibold text-gray-800 mb-1">CVS Pharmacy</h2>
      <p className="text-sm text-gray-500 mb-3">
        Download your Financial Summary from{' '}
        <span className="font-medium">cvs.com → Prescriptions → Financial Summary → Download</span>.
        Each prescription fill will be matched to a bank transaction and marked as an HSA-eligible prescription.
      </p>

      <div className="flex items-center gap-3 mb-4">
        <button
          onClick={() => inputRef.current?.click()}
          disabled={loading}
          data-testid="cvs-upload-button"
          className="text-sm font-medium px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {loading ? 'Importing…' : 'Upload CSV'}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={handleInputChange}
          data-testid="cvs-file-input"
        />
        {result && !loading && (
          <span className="text-sm text-gray-500">
            Matched {result.matched} of {result.row_count} fills
          </span>
        )}
      </div>

      {error && (
        <div
          data-testid="import-error"
          className="text-sm text-red-600 bg-red-50 border border-red-100 rounded px-3 py-2 mb-4"
        >
          {error}
        </div>
      )}

      {result && (
        <ImportResultTable result={result} onRelink={(updatedResult) => setResult(updatedResult)} />
      )}
    </div>
  )
}

function ImportResultTable({ result, onRelink }: { result: PharmacyImportResult; onRelink?: (r: PharmacyImportResult) => void }) {
  return (
    <div data-testid="import-result">
      <div className="flex gap-4 text-sm mb-3">
        <span className="text-green-700 font-medium">{result.matched} matched</span>
        {result.unmatched > 0 && (
          <span className="text-amber-600 font-medium">{result.unmatched} unmatched</span>
        )}
      </div>

      <div className="rounded border border-gray-100 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
            <tr>
              <th className="text-left px-3 py-2">Drug</th>
              <th className="text-left px-3 py-2 hidden sm:table-cell">Date</th>
              <th className="text-right px-3 py-2">Amount</th>
              <th className="text-left px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {result.fills.map(fill => (
              <tr key={fill.id} className="border-t border-gray-50">
                <td className="px-3 py-2 text-gray-900">
                  <div>{fill.drug_name}</div>
                  {fill.member_name && (
                    <div className="text-xs text-gray-400">{fill.member_name}</div>
                  )}
                </td>
                <td className="px-3 py-2 text-gray-500 hidden sm:table-cell">
                  {new Date(fill.fill_date + 'T00:00:00').toLocaleDateString('en-US', {
                    month: 'short', day: 'numeric', year: 'numeric',
                  })}
                </td>
                <td className="px-3 py-2 text-right text-gray-900">
                  ${parseFloat(fill.amount_paid).toFixed(2)}
                </td>
                <td className="px-3 py-2">
                  {fill.matched ? (
                    <span className="text-xs font-medium px-1.5 py-0.5 rounded bg-green-100 text-green-700">
                      Matched
                    </span>
                  ) : (
                    <span className="text-xs font-medium px-1.5 py-0.5 rounded bg-amber-100 text-amber-600">
                      Unmatched
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {result.unmatched > 0 && (
        <p className="text-xs text-gray-400 mt-2">
          Unmatched fills couldn't be linked to a transaction automatically. Open the matching transaction in the Transactions page and use the pharmacy fills panel to link manually.
        </p>
      )}
    </div>
  )
}
