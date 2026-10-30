"use client"

/** Error banner shown when an action fails. */

export function ErrorBanner({ message }: { message: string }) {
  return <div className="error-banner">{message}</div>
}
