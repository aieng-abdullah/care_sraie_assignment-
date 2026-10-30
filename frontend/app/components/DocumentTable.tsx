"use client"

/** Document list table with status filter, search, and row selection. */

import { useState, useEffect, useCallback } from "react"
import { listDocuments } from "../../lib/api"
import type { DocumentSummary } from "../../lib/api"
import { StatusBadge } from "./StatusBadge"
import { EmptyState } from "./EmptyState"
import { ErrorBanner } from "./ErrorBanner"

type DocumentTableProps = {
  onSelect: (doc: DocumentSummary) => void
  statusFilter?: string
  onStatusFilterChange?: (status: string) => void
  query?: string
  onQueryChange?: (query: string) => void
  refreshKey?: number
  page?: number
  pageSize?: number
}

export function DocumentTable({
  onSelect,
  statusFilter,
  onStatusFilterChange,
  query,
  onQueryChange,
  refreshKey = 0,
  page = 1,
  pageSize = 20,
}: DocumentTableProps) {
  const [docs, setDocs] = useState<DocumentSummary[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      try {
        const result = await listDocuments({
          q: query,
          status: statusFilter,
          page,
          page_size: pageSize,
        })
        if (!cancelled) {
          setDocs(result.items)
          setTotal(result.total)
          setError(null)
        }
      } catch (e: any) {
        if (!cancelled) setError(e.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [query, statusFilter, page, pageSize, refreshKey])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        Loading documents…
      </div>
    )
  }

  if (error) {
    return <ErrorBanner message={error} />
  }

  return (
    <>
      <div className="flex items-center gap-3 mb-4">
        <label className="label">
          <span className="label-text">Status filter</span>
          <select
            className="select"
            value={statusFilter || ""}
            onChange={(e) => onStatusFilterChange?.(e.target.value)}
          >
            <option value="">All</option>
            {["queued", "processing", "ok", "needs_review", "failed"].map((s) => (
              <option key={s} value={s}>
                {s.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </label>
        <label className="label flex-1 max-w-xs">
          <span className="label-text">Search filename</span>
          <input
            className="input"
            placeholder="Filename…"
            value={query || ""}
            onChange={(e) => onQueryChange?.(e.target.value)}
          />
        </label>
      </div>

      <div className="overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th>Filename</th>
              <th>Status</th>
              <th className="text-right">Pages</th>
              <th className="text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {docs.map((doc) => (
              <tr key={doc.id}>
                <td>
                  <a
                    href={`/document/${doc.id}`}
                    className="font-medium underline hover:underline-opacity-100"
                    onClick={(e) => {
                      e.preventDefault()
                      onSelect(doc)
                    }}
                  >
                    {doc.filename}
                  </a>
                </td>
                <td>
                  <StatusBadge status={doc.status} />
                </td>
                <td className="text-right">
                  {doc.page_count !== null ? doc.page_count : "—"}
                </td>
                <td className="text-right">
                  <button
                    onClick={(e) => {
                      e.preventDefault()
                      onSelect(doc)
                    }}
                    className="btn btn-ghost btn-sm"
                    aria-label={`View document ${doc.id}`}
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
            {docs.length === 0 && (
              <tr>
                <td colSpan={4} className="text-center py-8 text-muted-foreground">
                  No documents found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {total > pageSize && (
        <div className="flex justify-end mt-4 text-sm text-muted-foreground">
          Page {page} of {Math.ceil(total / pageSize)}
        </div>
      )}
    </>
  )
}
