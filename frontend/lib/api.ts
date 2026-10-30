/** Typed API client for the DocIntel backend. */

export interface DocumentSummary {
  id: string
  filename: string
  content_type: string
  size_bytes: number
  status: string
  page_count: number | null
  failure_reason: string | null
  created_at: Date
  updated_at: Date
}

export interface DocumentStatusResponse {
  id: string
  filename: string
  status: string
  pages_done: number
  pages_total: number | null
  failure_reason: string | null
  created_at: Date
  updated_at: Date
}

export interface ExtractionLineItem {
  description: string | null
  quantity: string | null
  unit_price: string | null
  amount: string | null
}

export interface ValidationIssueItem {
  code: string
  severity: string
  message: string
  context: Record<string, unknown> | null
}

export interface ExtractionResponse {
  document_id: string
  document_status: string
  invoice_number: string | null
  invoice_date: string | null // ISO date string YYYY-MM-DD
  supplier_name: string | null
  customer_name: string | null
  subtotal: string | null // Decimal serialized as string (no float artifacts)
  tax: string | null
  total: string | null
  currency: string | null // 3-letter ISO code
  status: string // "ok" | "needs_review"
  field_meta: { reason?: string } | null
  line_items: ExtractionLineItem[]
  validation_issues: ValidationIssueItem[]
}

export interface UploadResponse {
  items: UploadItem[]
}

export interface UploadItem {
  filename: string
  document_id: string | null
  content_type: string | null
  duplicate: boolean
  error: string | null
}

export interface CorrectionCreate {
  field: string
  new_value: string
  reason: string | null
}

export interface CorrectionResponse {
  document_id: string
  field: string
  old_value: string | null
  new_value: string
  reason: string | null
  validation_issues: ValidationIssueItem[]
}

export interface DocumentListResponse {
  items: DocumentSummary[]
  total: number
  page: number
  page_size: number
}

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export async function uploadFiles(files: File[]): Promise<UploadResponse> {
  const formData = new FormData()
  for (const file of files) {
    formData.append("files", file)
  }
  const res = await fetch(`${BASE_URL}/api/v1/documents`, {
    method: "POST",
    body: formData,
  })
  if (!res.ok) {
    const txt = await res.text()
    throw new Error(`Upload failed: ${res.status} ${txt}`)
  }
  return res.json()
}

export async function listDocuments(
  params: { q?: string; status?: string; page?: number; page_size?: number } = {},
): Promise<DocumentListResponse> {
  const url = new URL(`${BASE_URL}/api/v1/documents`)
  url.searchParams.set("page", (params.page ?? 1).toString())
  url.searchParams.set("page_size", (params.page_size ?? 20).toString())
  if (params.q) url.searchParams.set("q", params.q)
  if (params.status) url.searchParams.set("status", params.status)
  const res = await fetch(url)
  if (!res.ok) throw new Error(`List failed: ${res.status}`)
  return res.json()
}

export async function documentStatus(documentId: string): Promise<DocumentStatusResponse> {
  const res = await fetch(`${BASE_URL}/api/v1/documents/${documentId}/status`)
  if (!res.ok) throw new Error(`Status failed: ${res.status}`)
  return res.json()
}

export async function documentResults(documentId: string): Promise<ExtractionResponse> {
  const res = await fetch(`${BASE_URL}/api/v1/documents/${documentId}/results`)
  if (!res.ok) throw new Error(`Results failed: ${res.status}`)
  return res.json()
}

export async function documentCorrection(
  documentId: string,
  payload: CorrectionCreate,
): Promise<CorrectionResponse> {
  const res = await fetch(`${BASE_URL}/api/v1/documents/${documentId}/corrections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const txt = await res.text()
    throw new Error(`Correction failed: ${res.status} ${txt}`)
  }
  return res.json()
}