"use client"

/** Correction form for editing an extracted field. */

import type { CorrectionCreate } from "../../lib/api"
import { documentCorrection } from "../../lib/api"
import { useState } from "react"
import { ErrorBanner } from "./ErrorBanner"

type CorrectionFormProps = {
  documentId: string
  onApplied: () => void
}

export function CorrectionForm({ documentId, onApplied }: CorrectionFormProps) {
  const [field, setField] = useState<string>("invoice_number")
  const [newValue, setNewValue] = useState<string>("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fields: { value: string; label: string }[] = [
    { value: "invoice_number", label: "Invoice number" },
    { value: "invoice_date", label: "Invoice date" },
    { value: "supplier_name", label: "Supplier name" },
    { value: "customer_name", label: "Customer name" },
    { value: "subtotal", label: "Subtotal" },
    { value: "tax", label: "Tax" },
    { value: "total", label: "Total" },
    { value: "currency", label: "Currency" },
  ]

  const handleApply = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newValue.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      const payload: CorrectionCreate = {
        field,
        new_value: newValue,
        reason: "Client-side correction",
      }
      await documentCorrection(documentId, payload)
      onApplied()
      setNewValue("")
    } catch (err: any) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="card p-6 space-y-4">
      <h3 className="font-semibold">Correct a field</h3>
      {error && <ErrorBanner message={error} />}
      <form onSubmit={handleApply} className="space-y-3">
        <label className="label">
          <span className="label-text">Field</span>
          <select
            className="select"
            value={field}
            onChange={(e) => {
              setField(e.target.value)
              setNewValue("")
            }}
          >
            {fields.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </label>
        <label className="label">
          <span className="label-text">New value</span>
          <input
            className="input"
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
            placeholder="Enter new value"
            disabled={submitting}
          />
        </label>
        <button
          type="submit"
          className="btn btn-primary"
          disabled={submitting || !newValue.trim()}
        >
          {submitting ? "Applying…" : "Apply correction"}
        </button>
      </form>
    </section>
  )
}
