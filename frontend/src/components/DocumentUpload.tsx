import { useCallback, useEffect, useRef, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import imageCompression from 'browser-image-compression'
import { documentService, TransactionDocument } from '../services/documents'

interface Props {
  transactionId: string
  onCountChange: (count: number) => void
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

export default function DocumentUpload({ transactionId, onCountChange }: Props) {
  const [documents, setDocuments] = useState<TransactionDocument[]>([])
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Keep a ref to the latest onCountChange so the effect below never goes stale
  // without needing it as a dependency (avoids infinite loops if parent recreates the fn)
  const onCountChangeRef = useRef(onCountChange)
  useEffect(() => { onCountChangeRef.current = onCountChange })

  // Load existing documents on mount
  useEffect(() => {
    documentService.list(transactionId).then(setDocuments)
  }, [transactionId])

  // Notify parent whenever the document count changes — runs after render, never during
  useEffect(() => {
    onCountChangeRef.current(documents.length)
  }, [documents.length])

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return
    setUploading(true)
    setError(null)

    for (const file of acceptedFiles) {
      try {
        let uploadFile: File | Blob = file
        let contentType = file.type

        // Compress images client-side before upload
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

        const fileSize = uploadFile instanceof File ? uploadFile.size : uploadFile.size
        const filename = file.name

        // Step 1: get presigned PUT URL from backend
        const { document_id, upload_url } = await documentService.presign(transactionId, {
          filename,
          content_type: contentType,
          file_size_bytes: fileSize,
        })

        // Step 2: PUT directly to S3 (no auth header — plain fetch)
        const putResp = await documentService.putToS3(upload_url, uploadFile, contentType)
        if (!putResp.ok) {
          throw new Error(`S3 upload failed: ${putResp.status} ${putResp.statusText}`)
        }

        // Step 3: tell backend to confirm the upload
        const confirmed = await documentService.confirm(transactionId, document_id)

        setDocuments(prev => [...prev, confirmed])
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Upload failed. Please try again.'
        setError(message)
      }
    }

    setUploading(false)
  }, [transactionId])

  const handleDelete = async (doc: TransactionDocument) => {
    try {
      await documentService.delete(transactionId, doc.id)
      setDocuments(prev => prev.filter(d => d.id !== doc.id))
    } catch {
      setError('Failed to delete document. Please try again.')
    }
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: MAX_SIZE_MB * 1024 * 1024,
    multiple: true,
  })

  return (
    <div className="mt-2 space-y-2">
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
          <p className="text-sm text-blue-600">Drop files here</p>
        ) : (
          <p className="text-sm text-gray-500">
            Drop receipts here or <span className="text-blue-600 underline">click to browse</span>
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
            <li key={doc.id} className="flex items-center justify-between px-3 py-2 gap-2">
              <a
                href={doc.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline truncate flex-1"
              >
                {doc.original_filename}
              </a>
              <span className="text-xs text-gray-400 shrink-0">{formatBytes(doc.file_size_bytes)}</span>
              <button
                onClick={() => handleDelete(doc)}
                className="text-xs text-red-500 hover:text-red-700 shrink-0"
                aria-label={`Delete ${doc.original_filename}`}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}

      {documents.length === 0 && !uploading && (
        <p className="text-xs text-gray-400">No receipts attached yet.</p>
      )}
    </div>
  )
}
