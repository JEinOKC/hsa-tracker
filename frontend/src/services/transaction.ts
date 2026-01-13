/**
 * Transaction API service
 */

import api from './api'
import type {
  Transaction,
  TransactionCreate,
  TransactionUpdate,
  TransactionListResponse,
  TransactionFilters,
  Category,
  CategoryCreate,
  Receipt,
  ReceiptUploadUrl,
  ReceiptCreate,
  FamilyMember,
} from '../types/transaction'

class TransactionService {
  /**
   * List transactions with optional filters
   */
  async listTransactions(filters?: TransactionFilters): Promise<TransactionListResponse> {
    const response = await api.get<TransactionListResponse>('/transactions', {
      params: filters,
    })
    return response.data
  }

  /**
   * Get a single transaction by ID
   */
  async getTransaction(id: string): Promise<Transaction> {
    const response = await api.get<Transaction>(`/transactions/${id}`)
    return response.data
  }

  /**
   * Create a new transaction
   */
  async createTransaction(transaction: TransactionCreate): Promise<Transaction> {
    const response = await api.post<Transaction>('/transactions', transaction)
    return response.data
  }

  /**
   * Update a transaction
   */
  async updateTransaction(id: string, transaction: TransactionUpdate): Promise<Transaction> {
    const response = await api.put<Transaction>(`/transactions/${id}`, transaction)
    return response.data
  }

  /**
   * Delete a transaction
   */
  async deleteTransaction(id: string): Promise<void> {
    await api.delete(`/transactions/${id}`)
  }

  /**
   * List all categories (system + custom)
   */
  async listCategories(hsaEligibleOnly = false): Promise<Category[]> {
    const response = await api.get<Category[]>('/categories', {
      params: {
        hsa_eligible_only: hsaEligibleOnly,
      },
    })
    return response.data
  }

  /**
   * Create a custom category
   */
  async createCategory(category: CategoryCreate): Promise<Category> {
    const response = await api.post<Category>('/categories', category)
    return response.data
  }

  /**
   * Get upload URL for receipt
   */
  async getReceiptUploadUrl(
    transactionId: string,
    fileName: string,
    mimeType: string
  ): Promise<ReceiptUploadUrl> {
    const response = await api.post<ReceiptUploadUrl>('/receipts/upload-url', null, {
      params: {
        transaction_id: transactionId,
        file_name: fileName,
        mime_type: mimeType,
      },
    })
    return response.data
  }

  /**
   * Upload file to S3 using pre-signed URL
   */
  async uploadFileToS3(
    uploadUrl: string,
    fields: Record<string, string>,
    file: File
  ): Promise<void> {
    const formData = new FormData()

    // Add all fields from pre-signed URL
    Object.entries(fields).forEach(([key, value]) => {
      formData.append(key, value)
    })

    // Add the file last
    formData.append('file', file)

    // Upload directly to S3
    await fetch(uploadUrl, {
      method: 'POST',
      body: formData,
    })
  }

  /**
   * Create receipt record after uploading to S3
   */
  async createReceipt(transactionId: string, receipt: ReceiptCreate): Promise<Receipt> {
    const response = await api.post<Receipt>('/receipts', receipt, {
      params: {
        transaction_id: transactionId,
      },
    })
    return response.data
  }

  /**
   * Full receipt upload flow
   */
  async uploadReceipt(transactionId: string, file: File): Promise<Receipt> {
    // Step 1: Get pre-signed upload URL
    const uploadData = await this.getReceiptUploadUrl(
      transactionId,
      file.name,
      file.type
    )

    // Step 2: Upload file to S3
    await this.uploadFileToS3(uploadData.upload_url, uploadData.fields, file)

    // Step 3: Create receipt record in database
    const receipt = await this.createReceipt(transactionId, {
      file_name: file.name,
      file_size: file.size,
      mime_type: file.type,
      s3_key: uploadData.s3_key,
      s3_bucket: uploadData.fields.bucket || '',
    })

    return receipt
  }

  /**
   * List receipts for a transaction
   */
  async listReceipts(transactionId: string): Promise<Receipt[]> {
    const response = await api.get<Receipt[]>(`/receipts/transaction/${transactionId}`)
    return response.data
  }

  /**
   * Get download URL for receipt
   */
  async getReceiptDownloadUrl(receiptId: string): Promise<{
    download_url: string
    file_name: string
    mime_type: string
    expires_in: number
  }> {
    const response = await api.get(`/receipts/${receiptId}/download`)
    return response.data
  }

  /**
   * Delete a receipt
   */
  async deleteReceipt(receiptId: string): Promise<void> {
    await api.delete(`/receipts/${receiptId}`)
  }

  /**
   * Get current user's family members
   * (This would typically be in a separate family service)
   */
  async getFamilyMembers(): Promise<FamilyMember[]> {
    const response = await api.get<FamilyMember[]>('/family-members')
    return response.data
  }
}

export default new TransactionService()
