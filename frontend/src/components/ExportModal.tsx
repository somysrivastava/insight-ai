import { useState } from 'react'
import { useExportDataset } from '../hooks/useExport'
import { getErrorMessage } from '../api/client'
import { LoadingSpinner } from './LoadingSpinner'
import { ErrorBanner } from './ErrorBanner'
import type { ExportFormat, ExportSource } from '../types/api'

interface Props {
  datasetId: number
  filename: string
  lastQuestion?: string
  columns: string[]
  onClose: () => void
}

export function ExportModal({ datasetId, filename, lastQuestion, columns, onClose }: Props) {
  const [source, setSource] = useState<ExportSource>(lastQuestion ? 'query' : 'insights')
  const [format, setFormat] = useState<ExportFormat>('csv')
  const [groupBy, setGroupBy] = useState(columns[0] ?? '')
  const [done, setDone] = useState(false)
  const { mutate, isPending, error } = useExportDataset(datasetId)

  function handleExport() {
    mutate(
      { source, format, question: lastQuestion, group_by: groupBy, filename },
      { onSuccess: () => setDone(true) },
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-xl border border-border bg-surface p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-white">Export dataset</h2>

        <div className="mt-4 space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-300">What to export</label>
            <select
              value={source}
              onChange={(e) => setSource(e.target.value as ExportSource)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-100 outline-none focus:border-brand-500"
            >
              <option value="query" disabled={!lastQuestion}>
                Current query{lastQuestion ? ` — "${lastQuestion}"` : ' (ask a question first)'}
              </option>
              <option value="insights">Dataset insights</option>
              <option value="trends">Trends over time</option>
              <option value="breakdown">Breakdown by column</option>
            </select>
          </div>

          {source === 'breakdown' && (
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-300">Group by column</label>
              <select
                value={groupBy}
                onChange={(e) => setGroupBy(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-100 outline-none focus:border-brand-500"
              >
                {columns.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-300">Format</label>
            <div className="flex gap-2">
              {(['csv', 'xlsx', 'pdf'] as ExportFormat[]).map((f) => (
                <button
                  key={f}
                  onClick={() => setFormat(f)}
                  className={`flex-1 rounded-lg border px-3 py-2 text-sm font-medium uppercase ${
                    format === f
                      ? 'border-brand-500 bg-brand-600/15 text-brand-300'
                      : 'border-border text-slate-400 hover:bg-surface-hover'
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          {!!error && <ErrorBanner message={getErrorMessage(error)} />}
          {done && <p className="text-sm text-emerald-400">Downloaded.</p>}
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg px-4 py-2 text-sm font-medium text-slate-400 hover:bg-surface-hover">
            Close
          </button>
          <button
            onClick={handleExport}
            disabled={isPending || (source === 'query' && !lastQuestion)}
            className="flex items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-500 disabled:opacity-60"
          >
            {isPending ? <LoadingSpinner size="sm" /> : 'Export'}
          </button>
        </div>
      </div>
    </div>
  )
}
