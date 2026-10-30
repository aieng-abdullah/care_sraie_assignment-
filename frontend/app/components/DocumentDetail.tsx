"use client"

/** Document detail view: status, progress, extraction results, and corrections. */

import { useState, useEffect } from "react"
import { documentStatus, documentResults, documentCorrection } from "../../lib/api"
import type {
  DocumentSummary,
  DocumentStatusResponse,
  ExtractionResponse,
} from "../../lib/api"
import { StatusBadge } from "./StatusBadge"
import { ProgressBar } from "./ProgressBar"
import { ExtractionCard } from "./ExtractionCard"
import { CorrectionForm } from "./CorrectionForm"
import { EmptyState } from "./EmptyState"
import { ErrorBanner } from "./ErrorBanner"

type DocumentDetailProps = {
  document: DocumentSummary
}

export function DocumentDetail({ document }: DocumentDetailProps) {
  const [tab, setTab] = useState<"status" | "results" | "corrections">("status")
  const [status, setStatus] = useState<DocumentStatusResponse | null>(null)
  const [extraction, setExtraction] = useState<ExtractionResponse | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setIsLoading(true)
      try {
        const s = await documentStatus(document.id)
        if (!cancelled) setStatus(s)
      } catch (e: any) {
        if (!cancelled) setError(e.message)
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [document.id])

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const ext = await documentResults(document.id)
        if (!cancelled) setExtraction(ext)
      } catch {
        // Results may not exist yet while processing; ignore.
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [document.id, reloadKey])

  // Poll status while processing
  useEffect(() => {
    let timeout: NodeJS.Timeout
    if (status && status.status !== "ok" && status.status !== "failed") {
      timeout = setInterval(async () => {
        try {
          const s = await documentStatus(document.id)
          setStatus(s)
        } catch {
          // ignore polling errors
        }
      }, 3000)
    }
    return () => clearInterval(timeout)
  }, [status, document.id])

  if (isLoading && !status && !extraction) {
    return <EmptyState title="Loading…" />
  }

  if (error) {
    return <ErrorBanner message={error} />
  }

  const pageProgress =
    status?.pages_total !== null
      ? {
          done: status?.pages_done ?? 0,
          total: status?.pages_total ?? 0,
        }
      : null

  return (
    <section className="card p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">{document.filename}</h2>
        <StatusBadge status={status?.status || "queued"} />
      </div>

      {/* Status tab */}
      <div>
        <button
          onClick={() => setTab("status")}
          className={`px-3 py-2 rounded text-sm font-medium transition ${
            tab === "status"
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-primary"
          }`}
        >
          Processing status
        </button>
        <div className="mt-4 p-4 rounded border bg-card border-border space-y-3">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Status</p>
              <p className="text-lg font-medium">{status?.status || "queued"}</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Pages</p>
              <p className="text-lg font-medium">
                {status?.pages_done ?? 0} / {status?.pages_total ?? "—"}
              </p>
            </div>
          </div>
          {status?.failure_reason && (
            <p className="text-sm text-destructive">
              Failure: {status.failure_reason}
            </p>
          )}
          {pageProgress && status?.status !== "ok" && status?.status !== "failed" && (
            <ProgressBar done={pageProgress.done} total={pageProgress.total} />
          )}
        </div>
      </div>

      {/* Results tab */}
      <div>
        <button
          onClick={() => setTab("results")}
          className={`px-3 py-2 rounded text-sm font-medium transition ${
            tab === "results"
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-primary"
          }`}
        >
          Extracted data
        </button>
        <div className="mt-4">{tab === "results" ? <ExtractionCard extraction={extraction} status={status?.status || null} /> : null}</div>
      </div>

      {/* Corrections tab */}
      <div>
        <button
          onClick={() => setTab("corrections")}
          className={`px-3 py-2 rounded text-sm font-medium transition ${
            tab === "corrections"
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-primary"
          }`}
        >
          Corrections
        </button>
        <div className="mt-4">
          {tab === "corrections" ? (
            extraction &&
            (status?.status === "ok" || status?.status === "needs_review") ? (
              <CorrectionForm
                documentId={document.id}
                onApplied={() => setReloadKey((k) => k + 1)}
              />
            ) : (
              <EmptyState title="No corrections available" description="Corrections apply once extraction results exist." />
            )
          ) : null}
        </div>
      </div>
    </section>
  )
}
