"use client"

/** Upload area: file selection, in-progress indicator, per-item results. */

import * as React from "react"
import { UseUpload } from "./Upload"
import { StatusBadge } from "./StatusBadge"
import type { UploadItem } from "../../lib/api"

export function UploadZone() {
  const { progress, isSubmitting, fileInputRef, selectFiles, handleChange } = UseUpload({
    onUploadComplete: () => {},
  })

  return (
    <section className="card p-6 mb-6">
      <h2 className="font-semibold mb-4">Upload documents</h2>
      <div className="flex items-center gap-3 mb-4">
        <button
          onClick={selectFiles}
          className="btn btn-primary"
          disabled={isSubmitting}
          aria-label="Select files to upload"
        >
          {isSubmitting ? (
            <>
              <span className="spinner mr-2" aria-hidden="true"></span>
              Uploading…
            </>
          ) : (
            "Select files"
          )}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={handleChange}
        />
      </div>

      {progress.total > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium">{progress.accepted} accepted</span>
            {progress.failed > 0 && (
              <span className="text-sm text-destructive">{progress.failed} failed</span>
            )}
            <span className="text-muted-foreground">/{progress.total} files</span>
          </div>
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>File</th>
                  <th className="text-right">Status</th>
                </tr>
              </thead>
              <tbody>
                {progress.items.map((item: UploadItem) => (
                  <tr key={item.filename}>
                    <td>{item.filename}</td>
                    <td className="text-right">
                      {item.error ? (
                        <StatusBadge status="failed" />
                      ) : item.document_id ? (
                        <StatusBadge status="ok" />
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                      {item.error && <span className="text-xs text-destructive ml-2">{item.error}</span>}
                    </td>
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
