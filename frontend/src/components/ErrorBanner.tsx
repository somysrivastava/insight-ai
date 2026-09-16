interface Props {
  message: string
  onRetry?: () => void
}

export function ErrorBanner({ message, onRetry }: Props) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-red-900/50 bg-red-950/40 px-4 py-3 text-sm text-red-300">
      <span>{message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          className="shrink-0 rounded-md border border-red-800 px-2.5 py-1 text-xs font-medium text-red-200 hover:bg-red-900/40"
        >
          Retry
        </button>
      )}
    </div>
  )
}
