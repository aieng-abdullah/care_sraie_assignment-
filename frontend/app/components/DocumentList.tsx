"use client"

import { useState, useEffect, useCallback } from "react"
import { listDocuments } from "../../lib/api"

type DocumentListProps = {
  onSelect: (doc: any) => void
  statusFilter?: string
  query?: string
  page?: number
  pageSize?: number
}

export function DocumentList({ onSelect, statusFilter, query, page = 1, pageSize = 20 }: DocumentListProps) {
  const [docs, setDocs] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const result: any = await listDocuments({ q: query, status: statusFilter, page, page_size: pageSize })
        setDocs(result.items)
        setTotal(result.total)
      } catch (e: any) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [query, statusFilter, page, pageSize])

  const refresh = useCallback(() => {
    setLoading(true)
    ;(async () => {
      try {
        const result: any = await listDocuments({ q: query, status: statusFilter, page, page_size: pageSize })
        setDocs(result.items)
        setTotal(result.total)
      } catch (e: any) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    })()
  }, [query, statusFilter, page, pageSize])

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-muted-foreground">Loading documents…</div>
  }

  if (error) {
    return <div className="alert alert-error">{error}</div>
  }

  return (
    <>
      <div className="flex items-center gap-2 mb-4">
        <label className="label">
          <span className="label-text">Status filter</span>
          <select
            className="select select-bordered w-40"
            onChange={(e) => {}}
          >
            <option value="">All</option>
            {["queued", "processing", "ok", "needs_review", "failed"].map((s) => (
              <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
            ))}
          </select>
        </label>
        <label className="label">
          <span className="label-text">Search</span>
          <input
            className="input input-bordered w-60"
            placeholder="Filename…"
            value={query || ""}
            onChange={(e) => {}}
          />
        </label>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full caption-bottom">
          <thead>
            <tr>
              <th className="text-left">Filename</th>
              <th className="text-left">Status</th>
              <th className="text-right">Pages</th>
              <th className="text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {docs.map((doc: any) => (
              <tr key={doc.id} className="hover:bg-muted/50">
                <td>
                  <a
                    href={`/document/${doc.id}`}
                    className="underline hover:underline-opacity-100"
                    onClick={(e) => e.preventDefault()}
                  >
                    {doc.filename}
                  </a>
                </td>
                <td>
                  <span
                    className={`
                      px-2 py-0.5 rounded text-xs font-medium
                      ${doc.status === "ok" ? "bg-green-100 text-green-800" : doc.status === "needs_review" ? "bg-yellow-100 text-yellow-800" : doc.status === "processing" ? "bg-blue-100 text-blue-800" : "bg-red-100 text-red-800"}
                    `}
                  >
                    {doc.status}
                  </span>
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
                    className="btn btn-sm btn-ghost"
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

      {/* Pagination */}
      {total > pageSize && (
        <div className="flex justify-end mt-4">
          <span>
            Page {page} of {Math.ceil(total / pageSize)}
          </span>
        </div>
      )}
    </>
  )
}