"use client"

import * as React from "react"
import { useState, useEffect, useCallback } from "react"
import { uploadFiles } from "../../lib/api"

type UploadProgress = {
  accepted: number
  total: number
  failed: number
  items: UploadItem[]
}

export function UseUpload({ onUploadComplete }: { onUploadComplete: (items: UploadItem[]) => void }) {
  const [progress, setProgress] = useState<UploadProgress>({ accepted: 0, total: 0, failed: 0, items: [] })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const fileInputRef = React.createRef<HTMLInputElement>()

  const handleUpload = useCallback(async (files: File[]) => {
    setProgress({ accepted: 0, total: files.length, failed: 0, items: [] })
    setIsSubmitting(true)
    try {
      const result: { items: UploadItem[] } = await uploadFiles(files)
      setProgress(prev => ({
        ...prev,
        accepted: result.items.filter((i) => i.filename).length,
        failed: result.items.filter((i) => !i.filename).length,
        items: result.items,
      }))
      onUploadComplete(result.items)
    } catch (err) {
      console.error("Upload error:", err)
    } finally {
      setIsSubmitting(false)
    }
  }, [onUploadComplete])

  const selectFiles = useCallback(() => {
    fileInputRef.current?.click()
  }, [fileInputRef])

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files ? Array.from(e.target.files) : []
    if (files.length > 0) {
      handleUpload(files)
    }
    // Reset input to allow re-selecting same files
    e.target.value = ""
  }, [handleUpload])

  return {
    progress,
    isSubmitting,
    fileInputRef,
    handleUpload,
    selectFiles,
    handleChange,
  }
}

export interface UploadItem {
  filename: string
  document_id: string | null
  content_type: string | null
  duplicate: boolean
  error: string | null
}