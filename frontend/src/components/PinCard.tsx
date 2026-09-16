import { useState } from 'react'
import { useRefreshPin, useRemovePin } from '../hooks/useDashboards'
import { getErrorMessage } from '../api/client'
import { LoadingSpinner } from './LoadingSpinner'
import { ResultRenderer } from './ResultRenderer'
import type { DashboardPin, StructuredQueryResult } from '../types/api'

interface Props {
  dashboardId: number
  pin: DashboardPin
}

function isQueryShaped(result: Record<string, unknown> | null): result is { answer: string; data: StructuredQueryResult } {
  return !!result && 'data' in result && 'answer' in result
}

export function PinCard({ dashboardId, pin }: Props) {
  const [localError, setLocalError] = useState<string | null>(null)
  const refreshPin = useRefreshPin(dashboardId)
  const removePin = useRemovePin(dashboardId)

  const result = pin.cached_result
  const hasError = result && 'error' in result

  function handleRefresh() {
    setLocalError(null)
    refreshPin.mutate(pin.id, { onError: (err) => setLocalError(getErrorMessage(err)) })
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h3 className="font-medium text-slate-100">{pin.title}</h3>
          <p className="text-xs text-slate-500">
            {pin.last_refreshed_at ? `Refreshed ${new Date(pin.last_refreshed_at).toLocaleString()}` : 'Never refreshed'}
          </p>
        </div>
        <div className="flex shrink-0 gap-1">
          <button
            onClick={handleRefresh}
            disabled={refreshPin.isPending}
            title="Refresh"
            className="rounded-md border border-border p-1.5 text-slate-400 hover:bg-surface-hover hover:text-slate-200 disabled:opacity-50"
          >
            {refreshPin.isPending ? <LoadingSpinner size="sm" /> : <RefreshIcon className="h-4 w-4" />}
          </button>
          <button
            onClick={() => removePin.mutate(pin.id)}
            title="Remove pin"
            className="rounded-md border border-border p-1.5 text-slate-400 hover:bg-red-950/40 hover:text-red-300"
          >
            <TrashIcon className="h-4 w-4" />
          </button>
        </div>
      </div>

      {localError && <p className="mb-2 text-xs text-red-400">{localError}</p>}

      {hasError && (
        <p className="text-sm text-red-400">{String((result as { error: unknown }).error)}</p>
      )}

      {!hasError && isQueryShaped(result) && (
        <>
          <p className="mb-3 text-sm text-slate-300">{result.answer}</p>
          <ResultRenderer data={result.data} />
        </>
      )}

      {!hasError && result && !isQueryShaped(result) && (
        <pre className="max-h-48 overflow-auto rounded-lg bg-background p-3 text-xs text-slate-400">
          {JSON.stringify(result, null, 2)}
        </pre>
      )}

      {!result && <p className="text-sm text-slate-500">No result yet.</p>}
    </div>
  )
}

function RefreshIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} {...props}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
    </svg>
  )
}

function TrashIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} {...props}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
    </svg>
  )
}
