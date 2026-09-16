import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useDatasetSummary, useDictionary } from '../hooks/useDatasets'
import { useAskQuestion } from '../hooks/useAiQuery'
import { getErrorMessage } from '../api/client'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { ErrorBanner } from '../components/ErrorBanner'
import { ResultRenderer } from '../components/ResultRenderer'
import { ExportModal } from '../components/ExportModal'
import type { QueryResponse } from '../types/api'

export function DatasetDetailPage() {
  const { id } = useParams<{ id: string }>()
  const datasetId = Number(id)

  const { data: summary, isLoading: summaryLoading, isError: summaryError, error: summaryErr } =
    useDatasetSummary(datasetId)
  const { data: mappings } = useDictionary(datasetId)

  const [question, setQuestion] = useState('')
  const [lastQuestion, setLastQuestion] = useState('')
  const [result, setResult] = useState<QueryResponse | null>(null)
  const [showExport, setShowExport] = useState(false)
  const { mutate: ask, isPending, error: askError } = useAskQuestion(datasetId)

  function handleAsk(e: React.FormEvent) {
    e.preventDefault()
    if (!question.trim()) return
    ask(question, {
      onSuccess: (data) => {
        setResult(data)
        setLastQuestion(question)
      },
    })
  }

  const mappingByColumn = new Map((mappings ?? []).map((m) => [m.column_name, m]))

  return (
    <div>
      {summaryLoading && <LoadingSpinner label="Loading dataset…" />}
      {summaryError && <ErrorBanner message={getErrorMessage(summaryErr)} />}

      {summary && (
        <>
          <div className="mb-6 flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-white">{summary.filename}</h1>
              {summary.sheet_name && <p className="text-sm text-slate-500">Sheet: {summary.sheet_name}</p>}
              <div className="mt-1 flex gap-4 text-sm text-slate-400">
                <span>{summary.rows.toLocaleString('en-US')} rows</span>
                <span>{summary.columns} columns</span>
              </div>
            </div>
            <button
              onClick={() => setShowExport(true)}
              className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-slate-200 hover:bg-surface-hover"
            >
              Export
            </button>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[280px_1fr]">
            <div className="rounded-xl border border-border bg-surface p-4">
              <h2 className="mb-3 text-sm font-semibold text-slate-300">Columns</h2>
              <ul className="space-y-2.5">
                {summary.column_name.map((col) => {
                  const mapping = mappingByColumn.get(col)
                  return (
                    <li key={col} className="text-sm">
                      <div className="font-medium text-slate-200">{mapping?.display_name ?? col}</div>
                      <div className="flex flex-wrap items-center gap-x-2 text-xs text-slate-500">
                        <span className="font-mono">{col}</span>
                        <span>· {summary.data_types[col]}</span>
                        {mapping?.unit && <span>· {mapping.unit}</span>}
                      </div>
                      {mapping?.description && <p className="mt-0.5 text-xs text-slate-500">{mapping.description}</p>}
                    </li>
                  )
                })}
              </ul>
            </div>

            <div className="space-y-5">
              <form onSubmit={handleAsk} className="rounded-xl border border-border bg-surface p-4">
                <label className="mb-2 block text-sm font-semibold text-slate-300">Ask anything about your data</label>
                <div className="flex gap-2">
                  <input
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    placeholder="e.g. What is the total revenue by region?"
                    className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-100 outline-none focus:border-brand-500"
                  />
                  <button
                    type="submit"
                    disabled={isPending || !question.trim()}
                    className="flex items-center justify-center rounded-lg bg-brand-600 px-5 py-2 text-sm font-medium text-white hover:bg-brand-500 disabled:opacity-60"
                  >
                    {isPending ? <LoadingSpinner size="sm" /> : 'Ask'}
                  </button>
                </div>
              </form>

              {!!askError && <ErrorBanner message={getErrorMessage(askError)} />}

              {result && (
                <div className="rounded-xl border border-border bg-surface p-5">
                  <p className="mb-4 text-slate-200">{result.answer}</p>
                  <ResultRenderer data={result.data} />
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {showExport && (
        <ExportModal
          datasetId={datasetId}
          filename={summary?.filename?.replace(/\.[^.]+$/, '') ?? 'export'}
          lastQuestion={lastQuestion || undefined}
          columns={summary?.column_name ?? []}
          onClose={() => setShowExport(false)}
        />
      )}
    </div>
  )
}
