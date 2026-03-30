import api from './api'

export interface TransactionDocument {
  id: string
  transaction_id: string
  original_filename: string
  content_type: string
  file_size_bytes: number
  uploaded_at: string
  url: string
}

interface PresignResponse {
  document_id: string
  upload_url: string
  s3_key: string
}

export const documentService = {
  list: (transactionId: string): Promise<TransactionDocument[]> =>
    api.get<TransactionDocument[]>(`/bank/transactions/${transactionId}/documents`).then(r => r.data),

  presign: (
    transactionId: string,
    payload: { filename: string; content_type: string; file_size_bytes: number }
  ): Promise<PresignResponse> =>
    api.post<PresignResponse>(`/bank/transactions/${transactionId}/documents/presign`, payload).then(r => r.data),

  /**
   * PUT the file directly to S3 using the presigned URL.
   *
   * Uses plain fetch — NOT the Axios api client. The Axios interceptor would add
   * an Authorization header, which S3 presigned URLs reject.
   */
  putToS3: (uploadUrl: string, file: File | Blob, contentType: string): Promise<Response> =>
    fetch(uploadUrl, {
      method: 'PUT',
      body: file,
      headers: { 'Content-Type': contentType },
    }),

  confirm: (transactionId: string, documentId: string): Promise<TransactionDocument> =>
    api.post<TransactionDocument>(
      `/bank/transactions/${transactionId}/documents/${documentId}/confirm`
    ).then(r => r.data),

  delete: (transactionId: string, documentId: string): Promise<void> =>
    api.delete(`/bank/transactions/${transactionId}/documents/${documentId}`).then(() => undefined),
}
