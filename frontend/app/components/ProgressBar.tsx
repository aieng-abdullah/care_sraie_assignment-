"use client"

/** Page progress bar for large PDF processing. */

export function ProgressBar({ done, total }: { done: number; total: number }) {
  const percent = total > 0 ? (done / total) * 100 : 0
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{done} / {total} pages</span>
        <span>{percent.toFixed(0)}%</span>
      </div>
      <div className="progress-track">
        <div className="progress-bar" style={{ width: `${Math.min(percent, 100)}%` }} />
      </div>
    </div>
  )
}
