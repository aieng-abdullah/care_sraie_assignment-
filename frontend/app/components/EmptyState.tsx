"use client"

/** Empty state placeholder. */

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="empty-state">
      <p className="text-muted-foreground">{title}</p>
      {description && <p className="text-sm text-muted-foreground mt-1">{description}</p>}
    </div>
  )
}
