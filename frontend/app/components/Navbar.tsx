"use client"

/** Top navigation shell: app title and upload entry point. */

import Link from "next/link"

export function Navbar() {
  return (
    <header className="border-b border-border bg-background sticky top-0 z-20">
      <div className="flex items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-2">
          <span className="font-bold text-lg tracking-tight">DocIntel</span>
        </Link>
        <div className="flex items-center gap-3">
          <button className="btn btn-primary" aria-label="Upload documents">
            + Upload documents
          </button>
        </div>
      </div>
    </header>
  )
}
