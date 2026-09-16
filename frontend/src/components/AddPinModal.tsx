import { useState } from 'react'
import { useDatasets } from '../hooks/useDatasets'
import { useAddPin } from '../hooks/useDashboards'
import { getErrorMessage } from '../api/client'
import { LoadingSpinner } from './LoadingSpinner'
import { ErrorBanner } from './ErrorBanner'

interface Props {
  dashboardId: number
  onClose: () => void
}

export function AddPinModal({ dashboardId, onClose }: Props) {
  const { data: datasets } = useDatasets()
  const [datasetId, setDatasetId] = useState<number | ''>('')
  const [title, setTitle] = useState('')
  const [question, setQuestion] = useState('')
  const { mutate, isPending, error } = useAddPin(dashboardId)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!datasetId || !question.trim()) return
    mutate(
      {
        title: title.trim() || question.trim(),
        pinType: 'dataset_query',
        sourceId: datasetId,
        queryParams: { question: question.trim() },
      },
      { onSuccess: onClose },
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4" onClick={onClose}>
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md rounded-xl border border-border bg-surface p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-white">Pin a result</h2>

        <div className="mt-4 space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-300">Dataset</label>
            <select
              required
              value={datasetId}
              onChange={(e) => setDatasetId(Number(e.target.value))}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-100 outline-none focus:border-brand-500"
            >
              <option value="" disabled>
                Select a dataset…
              </option>
              {datasets?.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.filename}
                  {d.sheet_name ? ` — ${d.sheet_name}` : ''}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-300">Question</label>
            <input
              required
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. What is the total revenue by region?"
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-100 outline-none focus:border-brand-500"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-300">Title (optional)</label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Defaults to the question"
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-100 outline-none focus:border-brand-500"
            />
          </div>

          {!!error && <ErrorBanner message={getErrorMessage(error)} />}
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm font-medium text-slate-400 hover:bg-surface-hover"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isPending || !datasetId || !question.trim()}
            className="flex items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-500 disabled:opacity-60"
          >
            {isPending ? <LoadingSpinner size="sm" /> : 'Add pin'}
          </button>
        </div>
      </form>
    </div>
  )
}
