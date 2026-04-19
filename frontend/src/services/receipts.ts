import api from './api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PharmacyFill {
  id: string
  drug_name: string
  rx_number: string | null
  fill_date: string
  amount_paid: string
  pharmacy: string | null
  member_name: string | null
  transaction_id: string | null
  matched: boolean
}

export interface PharmacyImportResult {
  batch_id: string
  row_count: number
  matched: number
  unmatched: number
  fills: PharmacyFill[]
}

export interface ReceiptLineItem {
  id: string
  transaction_id: string
  description: string
  amount: string
  quantity: number
  is_hsa_eligible: boolean | null
  hsa_category: string | null
  source: 'csv_generic' | 'manual'
}

export interface LineItemImportResult {
  line_items: ReceiptLineItem[]
  eligible_total: string | null
  item_count: number
}

export interface LineItemCreate {
  description: string
  amount: string
  quantity?: number
  is_hsa_eligible?: boolean | null
  hsa_category?: string | null
}

export interface LineItemUpdate {
  description?: string
  amount?: string
  quantity?: number
  is_hsa_eligible?: boolean | null
  hsa_category?: string | null
}

// ---------------------------------------------------------------------------
// Service
// ---------------------------------------------------------------------------

export const receiptsService = {
  // --- CVS pharmacy import ---

  importCvsPharmacy: (file: File): Promise<PharmacyImportResult> => {
    const form = new FormData()
    form.append('file', file)
    return api.post<PharmacyImportResult>('/bank/imports/cvs-pharmacy', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data)
  },

  listPharmacyFills: (options?: { unmatched?: boolean }): Promise<PharmacyFill[]> => {
    const params = options?.unmatched ? { unmatched: true } : {}
    return api.get<PharmacyFill[]>('/bank/pharmacy-fills', { params }).then(r => r.data)
  },

  listTransactionFills: (transactionId: string): Promise<PharmacyFill[]> =>
    api.get<PharmacyFill[]>(`/bank/transactions/${transactionId}/pharmacy-fills`).then(r => r.data),

  linkFill: (fillId: string, transactionId: string): Promise<void> =>
    api.post(`/bank/pharmacy-fills/${fillId}/link`, { transaction_id: transactionId }).then(() => undefined),

  unlinkFill: (fillId: string): Promise<void> =>
    api.delete(`/bank/pharmacy-fills/${fillId}/link`).then(() => undefined),

  // --- Generic line items ---

  importLineItemsCsv: (transactionId: string, file: File): Promise<LineItemImportResult> => {
    const form = new FormData()
    form.append('file', file)
    return api.post<LineItemImportResult>(
      `/bank/transactions/${transactionId}/line-items/import-csv`,
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    ).then(r => r.data)
  },

  listLineItems: (transactionId: string): Promise<ReceiptLineItem[]> =>
    api.get<ReceiptLineItem[]>(`/bank/transactions/${transactionId}/line-items`).then(r => r.data),

  createLineItem: (transactionId: string, item: LineItemCreate): Promise<ReceiptLineItem> =>
    api.post<ReceiptLineItem>(`/bank/transactions/${transactionId}/line-items`, item).then(r => r.data),

  updateLineItem: (transactionId: string, itemId: string, patch: LineItemUpdate): Promise<ReceiptLineItem> =>
    api.patch<ReceiptLineItem>(`/bank/transactions/${transactionId}/line-items/${itemId}`, patch).then(r => r.data),

  deleteLineItem: (transactionId: string, itemId: string): Promise<void> =>
    api.delete(`/bank/transactions/${transactionId}/line-items/${itemId}`).then(() => undefined),

  // --- CSV template ---

  downloadLineItemsTemplate: (): void => {
    window.open('/api/v1/bank/imports/line-items-template.csv', '_blank')
  },
}
