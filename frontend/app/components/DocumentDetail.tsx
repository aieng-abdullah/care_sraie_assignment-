"use client"

import { useState, useEffect } from "react"
import { UseUpload } from "./Upload"
import { DocumentList } from "./DocumentList"
import { documentStatus, documentResults, documentCorrection } from "../../lib/api"
import type { DocumentStatusResponse, ExtractionResponse, CorrectionResponse } from "../../lib/api"

export default function Dashboard() {
  const [selectedDoc, setSelectedDoc] = useState<DocumentSummary | null>(null)
  const { progress, isSubmitting, selectFiles, handleChange } = UseUpload({
    onUploadComplete: (items) => {
      const accepted = items.find((i) => i.document_id)
      if (accepted) {
        setSelectedDoc({
          id: accepted.document_id,
          filename: accepted.filename,
          content_type: "",
          size_bytes: 0,
          status: "queued",
          page_count: null,
          failure_reason: null,
          created_at: new Date(),
          updated_at: new Date(),
        } as DocumentSummary)
      }
    },
  })

  // Fetch status for the selected document periodically
  useEffect(() => {
    let timeout: NodeJS.Timeout
    if (selectedDoc) {
      timeout = setInterval(async () => {
        try {
          const status = await documentStatus(selectedDoc.id)
          setSelectedDoc((prev) => {
            if (!prev || prev.id !== selectedDoc.id) return prev
            return { ...prev, status: status.status, pages_done: status.pages_done, pages_total: status.pages_total, failure_reason: status.failure_reason }
          })
        } catch (e) {
          // ignore errors during polling
        }
      }, 3000)
    }
    return () => clearInterval(timeout)
  }, [selectedDoc?.id])

  const handleSelect = (doc: DocumentSummary) => {
    setSelectedDoc(doc)
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-accent/60">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <h1 className="text-2xl font-bold">DocIntel</h1>
          <div className="flex items-center gap-3">
            <button
              onClick={() => selectFiles()}
              className="btn btn-ghost btn-sm"
              aria-label="Upload documents"
            >
              + Upload
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-6">
        {/* Upload status indicator */}
        {progress.total > 0 && (
          <div className="mb-4 p-4 rounded border" style={{
            background: progress.items.some(i => i.error) ? "var(--destructive)" : "var(--card)",
            border: "1px solid var(--border)",
          }}>
            <div className="flex items-center gap-3">
              <span className="font-medium">{progress.accepted} accepted</span>
              {progress.failed > 0 && (
                <span className="text-sm text-destructive">• {progress.failed} failed</span>
              )}
              <span className="text-xs text-muted-foreground">/{progress.total} files</span>
            </div>
          </div>
        )}

        {/* Document list and detail view */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left: Document list */}
          <div className="space-y-4">
            <DocumentList onSelect={handleSelect} />
          </div>

          {/* Right: Document detail / results */}
          {selectedDoc ? (
            <DocumentDetail document={selectedDoc} />
          ) : (
            <div className="p-6 text-muted-foreground">
              <p>Select a document from the list to view details.</p>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

interface DocumentSummary {
  id: string
  filename: string
  document_id?: string
}

interface DocumentDetailProps {
  document: DocumentSummary
}

function DocumentDetail({ document }: DocumentDetailProps) {
  const [tab, setTab] = useState<"status" | "results" | "corrections">("status")
  const [status, setStatus] = useState<DocumentStatusResponse | null>(null)
  const [extraction, setExtraction] = useState<ExtractionResponse | null>(null)
  const [corrections, setCorrections] = useState<CorrectionResponse[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [correctionField, setCorrectionField] = useState<string>("invoice_number")
  const [correctionNewValue, setCorrectionNewValue] = useState<string>("")

  // Load status on mount
  useEffect(() => {
    async function load() {
      setIsLoading(true)
      try {
        const s = await documentStatus(document.id)
        setStatus(s)
      } catch (e: any) {
        setError(e.message)
      } finally {
        setIsLoading(false)
      }
    }
    load()
  }, [document.id])

  // Load extraction results
  useEffect(() => {
    async function load() {
      setIsLoading(true)
      try {
        const ext = await documentResults(document.id)
        setExtraction(ext)
      } catch (e: any) {
        setError(e.message)
      } finally {
        setIsLoading(false)
      }
    }
    load()
  }, [document.id])

  // Load corrections history (would need an endpoint, stubbed)
  useEffect(() => {
    // TODO: fetch from /api/v1/documents/{id}/corrections history
  }, [document.id])

  // Compute display helpers
  const hasExtraction = extraction !== null
  const isOk = status?.status === "ok"
  const isNeedsReview = status?.status === "needs_review"
  const isProcessing = status?.status === "processing"
  const hasFailure = !!status?.failure_reason

  // Page progress display
  const pageProgress = status?.pages_total !== null ? {
    done: status?.pages_done ?? 0,
    total: status?.pages_total,
    percent: status?.pages_done != null ? (status.pages_done / Math.max(status.pages_total, 1)) * 100 : 0,
  } : null

  if (!status && !hasExtraction) {
    return <div className="p-6 text-muted-foreground">Loading…</div>
  }

  return (
    <div className="space-y-4">
      {/* Status tab */}
      <div>
        <button
          onClick={() => setTab("status")}
          className={`
            px-3 py-2 rounded text-sm font-medium
            ${tab === "status" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-primary"}
          `}
        >
          Processing Status
        </button>

        <div className="mt-4 p-4 rounded border" style={{
          background: "var(--card)",
          border: "1px solid var(--border)",
        }}>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-muted-foreground">Status</p>
              <p className={`
                text-lg font-medium ${isOk ? "text-green-600" : isNeedsReview ? "text-yellow-600" : isProcessing ? "text-blue-600" : "text-red-600"}
              `}>
                {status?.status}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Pages</p>
              <p className="text-lg font-medium">
                {status?.pages_done ?? 0} / {status?.pages_total ?? "—"}
              </p>
            </div>
          </div>

          {hasFailure && (
            <p className="mt-2 text-sm text-destructive">Failure: {status?.failure_reason}</p>
          )}

          {/* Page progress bar */}
          {status?.pages_total !== null && !isOk && !isNeedsReview && (
            <div className="mt-4">
              <p className="text-sm text-muted-foreground mb-2">Page progress</p>
              <div className="bg-muted/50 rounded h-2">
                <div
                  className={`h-full rounded bg-blue-600 transition-width ${isProcessing ? "animate-pulse" : ""}`}
                  style={{ width: `${pageProgress?.percent || 0}%` }}
                >
                  &nbsp;
                </div>
              </div>
              <div className="flex text-xs text-muted-foreground">
                <span>{status?.pages_done ?? 0}</span>
                <span>/</span>
                <span>{status?.pages_total ?? "?"}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Results tab */}
      <div>
        <button
          onClick={() => setTab("results")}
          className={`
            px-3 py-2 rounded text-sm font-medium
            ${tab === "results" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-primary"}
          `}
        >
          Extracted Data
        </button>

        {hasExtraction ? (
          <div className="mt-4 space-y-4">
            <div>
              <p className="text-sm text-muted-foreground">Invoice Number</p>
              <p className="text-lg font-medium">{extraction?.invoice_number || "—"}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Invoice Date</p>
              <p className="text-lg font-medium">{extraction?.invoice_date || "—"}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Supplier</p>
              <p className="text-lg font-medium">{extraction?.supplier_name || "—"}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Customer</p>
              <p className="text-lg font-medium">{extraction?.customer_name || "—"}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Currency</p>
              <p className="text-lg font-medium">{extraction?.currency || "—"}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Total</p>
              <p className="text-lg font-medium">
                {extraction?.total !== null ? `$${extraction.total.toString()}` : "—"}
              </p>
            </div>

            {extraction?.line_items && extraction?.line_items.length > 0 && (
              <div>
                <p className="text-sm text-muted-foreground">Line Items ({extraction.line_items.length})</p>
                <div className="mt-2 space-y-2 max-h-40 overflow-y-auto">
                  {extraction.line_items.map((li, i) => (
                    <div key={i} className="p-3 rounded border">
                      <p className="font-medium">{li.description || "—"}</p>
                      <p className="text-xs text-muted-foreground">
                        Qty: {li.quantity?.toString() || "—"} • Unit: {li.unit_price?.toString() || "—"} • Amt: {li.amount?.toString() || "—"}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {extraction?.field_meta && extraction?.field_meta.reason && (
              <p className="mt-2 text-sm text-destructive">Reason: {extraction.field_meta.reason}</p>
            )}

            {/* Validation status */}
            {extraction?.status === "needs_review" && (
              <p className="mt-2 text-sm text-destructive">
                Validation errors detected — document requires review
              </p>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No extraction results yet</p>
        )}
      </div>

      {/* Corrections tab */}
      <div>
        <button
          onClick={() => setTab("corrections")}
          className={`
            px-3 py-2 rounded text-sm font-medium
            ${tab === "corrections" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-primary"}
          `}
        >
          Corrections
        </button>

        {corrections.length > 0 ? (
          <div className="mt-4">
            <p className="text-sm text-muted-foreground">Corrections history</p>
            <div className="mt-2 space-y-2 max-h-40 overflow-y-auto">
              {corrections.map((c, i) => (
                <div key={i} className="p-3 rounded border">
                  <p className="font-medium">{c.field}</p>
                  <p className="text-xs text-muted-foreground">
                    {c.old_value || "—"} → {c.new_value}
                  </p>
                  <p className="text-xs text-muted-foreground">{c.reason || ""}</p>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No corrections yet</p>
        )}

        {tab === "corrections" && hasExtraction && isNeedsReview && (
          <div className="mt-4 p-4 rounded border" style={{
            background: "var(--card)",
            border: "1px solid var(--border)",
          }}>
            <h3 className="font-medium mb-3">Correct a field</h3>
            <select
              className="select select-bordered w-full mb-3"
              onChange={(e) => {
                setCorrectionField(e.target.value as string)
                setCorrectionNewValue("")
              }}
            >
              <option value="invoice_number">Invoice number</option>
              <option value="invoice_date">Invoice date</option>
              <option value="supplier_name">Supplier name</option>
              <option value="customer_name">Customer name</option>
              <option value="subtotal">Subtotal</option>
              <option value="tax">Tax</option>
              <option value="total">Total</option>
              <option value="currency">Currency</option>
            </select>

            <div className="mb-3">
              <label className="label">
                <span className="label-text">New value</span>
                <input
                  className="input input-bordered w-full"
                  value={correctionNewValue}
                  onChange={(e) => setCorrectionNewValue(e.target.value)}
                  placeholder="Enter new value"
                />
              </label>
            </div>

            <button
              onClick={() => {
                if (!correctionField || !correctionNewValue.trim()) return
                documentCorrection(document.id, {
                  field: correctionField,
                  new_value: correctionNewValue,
                  reason: "Client-side correction",
                }).then(() => {
                  // Refresh data after correction
                  setTab("status")
                  ;(async () => {
                    const s = await documentStatus(document.id)
                    setStatus(s)
                    const e = await documentResults(document.id)
                    setExtraction(e)
                  })()
                }).catch((err) => {
                  setError(err.message)
                })
              }}
              className="btn btn-primary"
            >
              Apply Correction
            </button>
          </div>
        )}
      </div>
    </div>
  )
}