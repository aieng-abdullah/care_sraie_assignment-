"use client"

/** App shell: navbar, upload zone, document list, and selected document detail. */

import { useState } from "react"
import { Navbar } from "./components/Navbar"
import { UploadZone } from "./components/UploadZone"
import { DocumentTable } from "./components/DocumentTable"
import { DocumentDetail } from "./components/DocumentDetail"
import { EmptyState } from "./components/EmptyState"
import type { DocumentSummary } from "../lib/api"

export default function Page() {
  const [selectedDoc, setSelectedDoc] = useState<DocumentSummary | null>(null)

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="max-w-5xl mx-auto p-6">
        <section className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-4 space-y-6">
            <UploadZone />
            <DocumentTable onSelect={setSelectedDoc} />
          </div>
          <div className="lg:col-span-8">
            {selectedDoc ? (
              <DocumentDetail document={selectedDoc} />
            ) : (
              <div className="card p-12">
                <EmptyState title="Select a document" description="Pick a document from the list to inspect its extraction, validation issues, and corrections." />
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  )
}
