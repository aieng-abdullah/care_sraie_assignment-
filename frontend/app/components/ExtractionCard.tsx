"use client"

/** Extraction results card: header fields, validation status, and line items. */

import type { ExtractionResponse } from "../../lib/api"
import { StatusBadge } from "./StatusBadge"
import { EmptyState } from "./EmptyState"

type ExtractionCardProps = {
  extraction: ExtractionResponse | null
  status: string | null
}

/** Display a Decimal-as-string money value trimmed of trailing zeros. */
function fmtMoney(value: string | null): string {
  if (value === null) return "—"
  return value.replace(/0+$/, "").replace(/\.$/, "")
}

export function ExtractionCard({ extraction, status }: ExtractionCardProps) {
  if (!extraction) {
    return <EmptyState title="No extraction results yet" description="Processing may still be running." />
  }

  const isNeedsReview = extraction.status === "needs_review"

  return (
    <section className="card p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">Extracted data</h2>
        <StatusBadge status={isNeedsReview ? "needs_review" : status || "ok"} />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">Invoice number</p>
          <p className="font-medium">{extraction.invoice_number || "—"}</p>
        </div>
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">Invoice date</p>
          <p className="font-medium">{extraction.invoice_date || "—"}</p>
        </div>
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">Supplier</p>
          <p className="font-medium">{extraction.supplier_name || "—"}</p>
        </div>
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">Customer</p>
          <p className="font-medium">{extraction.customer_name || "—"}</p>
        </div>
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">Currency</p>
          <p className="font-medium">{extraction.currency || "—"}</p>
        </div>
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">Total</p>
          <p className="font-medium">
            {extraction.total !== null ? `$${fmtMoney(extraction.total)}` : "—"}
          </p>
        </div>
      </div>

      {extraction.validation_issues.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground font-medium">Validation issues</p>
          <ul className="space-y-2">
            {extraction.validation_issues.map((issue, i) => (
              <li
                key={`${issue.code}-${i}`}
                className="p-3 rounded border text-sm text-destructive bg-destructive/5 border-destructive/30"
              >
                <span className="font-medium capitalize">{issue.code.replace(/_/g, " ")}</span>
                {" — "}
                {issue.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      {extraction.field_meta?.reason && (
        <div className="p-3 rounded bg-amber-50 border border-amber-100 text-sm text-amber-800">
          {extraction.field_meta.reason}
        </div>
      )}

      {isNeedsReview && (
        <p className="text-sm text-destructive font-medium">
          Validation errors detected — document requires review
        </p>
      )}

      {extraction.line_items && extraction.line_items.length > 0 && (
        <div>
          <p className="text-xs text-muted-foreground font-medium">
            Line items ({extraction.line_items.length})
          </p>
          <div className="mt-2 overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>Description</th>
                  <th className="text-right">Qty</th>
                  <th className="text-right">Unit price</th>
                  <th className="text-right">Amount</th>
                </tr>
              </thead>
              <tbody>
                {extraction.line_items.map((li, i) => (
                  <tr key={i}>
                    <td>{li.description || "—"}</td>
                    <td className="text-right">{li.quantity?.toString() || "—"}</td>
                    <td className="text-right">{li.unit_price?.toString() || "—"}</td>
                    <td className="text-right">{li.amount?.toString() || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  )
}
