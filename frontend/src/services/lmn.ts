import api from './api'

export interface LmnDocument {
  id: string
  family_member_id: string
  family_member_name: string
  original_filename: string
  content_type: string
  file_size_bytes: number
  label: string | null
  provider_name: string | null
  issue_date: string | null
  expiration_date: string | null
  notes: string | null
  uploaded_at: string
  url: string
}

interface LmnPresignRequest {
  filename: string
  content_type: string
  file_size_bytes: number
  label?: string
  provider_name?: string
  issue_date?: string
  expiration_date?: string
  notes?: string
}

interface LmnPresignResponse {
  lmn_id: string
  upload_url: string
  s3_key: string
}

export interface LmnDocumentUpdate {
  label?: string | null
  provider_name?: string | null
  issue_date?: string | null
  expiration_date?: string | null
  notes?: string | null
}

export const lmnService = {
  list: (memberId: string): Promise<LmnDocument[]> =>
    api.get<LmnDocument[]>(`/families/${memberId}/lmn`).then(r => r.data),

  listAll: (): Promise<LmnDocument[]> =>
    api.get<LmnDocument[]>('/families/lmn').then(r => r.data),

  presign: (memberId: string, payload: LmnPresignRequest): Promise<LmnPresignResponse> =>
    api.post<LmnPresignResponse>(`/families/${memberId}/lmn/presign`, payload).then(r => r.data),

  putToS3: (uploadUrl: string, file: File | Blob, contentType: string): Promise<Response> =>
    fetch(uploadUrl, {
      method: 'PUT',
      body: file,
      headers: { 'Content-Type': contentType },
    }),

  confirm: (memberId: string, lmnId: string): Promise<LmnDocument> =>
    api.post<LmnDocument>(`/families/${memberId}/lmn/${lmnId}/confirm`).then(r => r.data),

  update: (memberId: string, lmnId: string, payload: LmnDocumentUpdate): Promise<LmnDocument> =>
    api.patch<LmnDocument>(`/families/${memberId}/lmn/${lmnId}`, payload).then(r => r.data),

  delete: (memberId: string, lmnId: string): Promise<void> =>
    api.delete(`/families/${memberId}/lmn/${lmnId}`).then(() => undefined),
}
