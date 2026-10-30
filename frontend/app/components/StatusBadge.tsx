"use client"

/** Status pill showing a document's processing state. */

import type { DocumentStatusResponse } from "../../lib/api"

export function StatusBadge({ status }: { status: string }) {
  const variant =
    status === "ok"
      ? "status-ok"
      : status === "needs_review"
        ? "status-needs-review"
        : status === "processing"
          ? "status-processing"
          : "status-failed"
  return (
    <span className={`badge ${variant}`}>{status.replace(/_/g, " ")}</span>
  )
}
