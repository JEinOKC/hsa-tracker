import { useCallback, useEffect, useRef, useState } from 'react'
import { XIcon } from './icons'
import { useDropzone } from 'react-dropzone'
import imageCompression from 'browser-image-compression'
import { lmnService, LmnDocument } from '../services/lmn'

interface Props {
  familyMemberId: string
  onCountChange?: (count: number) => void
}

const ACCEPTED_TYPES = {
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
  'image/heic': ['.heic'],
  'application/pdf': ['.pdf'],
}
const IMAGE_TYPES = new Set(['image/jpeg', 'image/png', 'image/heic'])
const MAX_SIZE_MB = 10

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return ''
  return new Date(dateStr + 'T00:00:00').toLocaleDateString()
}

export default function LmnUpload({ familyMemberId, onCountChange }: Props) {
  const [documents, setDocuments] = useState<LmnDocument[]>([])
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)

  // Metadata form state
  const [label, setLabel] = useState('')
  const [providerName, setProviderName] = useState('')
  const [issueDate, setIssueDate] = useState('')
  const [expirationDate, setExpirationDate] = useState('')
  const [notes, setNotes] = useState('')

  const onCountChangeRef = useRef(onCountChange)
  useEffect(() => { onCountChangeRef.current = onCountChange })

  useEffect(() => {
    lmnService.list(familyMemberId).then(setDocuments).catch(() => {})
  }, [familyMemberId])

  useEffect(() => {
    onCountChangeRef.current?.(documents.length)
  }, [documents.length])

  const resetForm = () => {
    setLabel('')
    setProviderName('')
    setIssueDate('')
    setExpirationDate('')
    setNotes('')
    setShowForm(false)
  }

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return
    setUploading(true)
    setError(null)

    for (const file of acceptedFiles) {
      try {
        let uploadFile: File | Blob = file
        let contentType = file.type

        if (IMAGE_TYPES.has(file.type)) {
          const compressed = await imageCompression(file, {
            maxWidthOrHeight: 2000,
            useWebWorker: true,
            fileType: 'image/jpeg',
            initialQuality: 0.85,
          })
          uploadFile = compressed
          contentType = 'image/jpeg'
        }

        const fileSize = uploadFile.size
        const filename = file.name

        const { lmn_id, upload_url } = await lmnService.presign(familyMemberId, {
          filename,
          content_type: contentType,
          file_size_bytes: fileSize,
          ...(label && { label }),
          ...(providerName && { provider_name: providerName }),
          ...(issueDate && { issue_date: issueDate }),
          ...(expirationDate && { expiration_date: expirationDate }),
          ...(notes && { notes }),
        })

        const putResp = await lmnService.putToS3(upload_url, uploadFile, contentType)
        if (!putResp.ok) {
          throw new Error(`S3 upload failed: ${putResp.status} ${putResp.statusText}`)
        }

        const confirmed = await lmnService.confirm(familyMemberId, lmn_id)
        setDocuments(prev => [confirmed, ...prev])
        resetForm()
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Upload failed. Please try again.'
        setError(message)
      }
    }

    setUploading(false)
  }, [familyMemberId, label, providerName, issueDate, expirationDate, notes])

  const handleDelete = async (doc: LmnDocument) => {
    try {
      await lmnService.delete(familyMemberId, doc.id)
      setDocuments(prev => prev.filter(d => d.id !== doc.id))
    } catch {
      setError('Failed to delete document. Please try again.')
    }
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: MAX_SIZE_MB * 1024 * 1024,
    multiple: false,
  })

  return (
    <div className="space-y-2">
      {/* Optional metadata form */}
      {!showForm ? (
        <button
          type="button"
          onClick={() => setShowForm(true)}
          className="text-xs text-blue-600 hover:underline"
        >
          + Add metadata before uploading
        </button>
      ) : (
        <div className="space-y-2 rounded border border-gray-200 bg-gray-50 p-3">
          <div className="grid grid-cols-2 gap-2">
            <input
              type="text"
              placeholder="Label (e.g. Orthodontic LMN)"
              value={label}
              onChange={e => setLabel(e.target.value)}
              className="rounded border border-gray-300 px-2 py-1 text-sm"
            />
            <input
              type="text"
              placeholder="Provider name"
              value={providerName}
              onChange={e => setProviderName(e.target.value)}
              className="rounded border border-gray-300 px-2 py-1 text-sm"
            />
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Issue date</label>
              <input
                type="date"
                value={issueDate}
                onChange={e => setIssueDate(e.target.value)}
                className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Expiration date</label>
              <input
                type="date"
                value={expirationDate}
                onChange={e => setExpirationDate(e.target.value)}
                className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
              />
            </div>
          </div>
          <input
            type="text"
            placeholder="Notes (optional)"
            value={notes}
            onChange={e => setNotes(e.target.value)}
            className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
          />
          <button
            type="button"
            onClick={resetForm}
            className="text-xs text-gray-500 hover:underline"
          >
            Cancel
          </button>
        </div>
      )}

      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg px-4 py-3 text-center cursor-pointer transition-colors ${
          isDragActive
            ? 'border-blue-400 bg-blue-50'
            : 'border-gray-300 hover:border-gray-400 bg-gray-50'
        }`}
      >
        <input {...getInputProps()} />
        {uploading ? (
          <p className="text-sm text-gray-500">Uploading…</p>
        ) : isDragActive ? (
          <p className="text-sm text-blue-600">Drop file here</p>
        ) : (
          <p className="text-sm text-gray-500">
            Drop LMN here or <span className="text-blue-600 underline">click to browse</span>
            <br />
            <span className="text-xs text-gray-400">JPEG, PNG, HEIC, or PDF · max {MAX_SIZE_MB} MB</span>
          </p>
        )}
      </div>

      {error && (
        <p className="text-xs text-red-600">{error}</p>
      )}

      {/* Document list */}
      {documents.length > 0 && (
        <ul className="divide-y divide-gray-100 rounded border border-gray-200 bg-white text-sm">
          {documents.map(doc => (
            <li key={doc.id} className="px-3 py-2">
              <div className="flex items-center justify-between gap-2">
                <a
                  href={doc.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline truncate flex-1"
                >
                  {doc.label || doc.original_filename}
                </a>
                <span className="text-xs text-gray-400 shrink-0">{formatBytes(doc.file_size_bytes)}</span>
                <button
                  onClick={() => handleDelete(doc)}
                  className="text-xs text-red-500 hover:text-red-700 shrink-0"
                  aria-label={`Delete ${doc.original_filename}`}
                >
                  <XIcon className="w-3.5 h-3.5" />
                </button>
              </div>
              {(doc.provider_name || doc.issue_date || doc.expiration_date) && (
                <div className="text-xs text-gray-500 mt-1 flex gap-3">
                  {doc.provider_name && <span>Dr. {doc.provider_name}</span>}
                  {doc.issue_date && <span>Issued: {formatDate(doc.issue_date)}</span>}
                  {doc.expiration_date && <span>Expires: {formatDate(doc.expiration_date)}</span>}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {documents.length === 0 && !uploading && (
        <p className="text-xs text-gray-400">No letters of medical necessity attached.</p>
      )}
    </div>
  )
}
