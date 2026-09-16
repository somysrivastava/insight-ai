import { Link } from 'react-router-dom'
import { useDatasets } from '../hooks/useDatasets'
import { getErrorMessage } from '../api/client'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { ErrorBanner } from '../components/ErrorBanner'

export function DatasetsListPage() {
  const { data: datasets, isLoading, isError, error, refetch } = useDatasets()

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Datasets</h1>
          <p className="mt-1 text-sm text-slate-500">Upload a file, then ask questions about it in plain English.</p>
        </div>
        <Link
          to="/datasets/upload"
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-500"
        >
          Upload dataset
        </Link>
      </div>

      {isLoading && <LoadingSpinner label="Loading datasets…" />}
      {isError && <ErrorBanner message={getErrorMessage(error)} onRetry={() => refetch()} />}

      {datasets && datasets.length === 0 && (
        <div className="rounded-xl border border-dashed border-border px-6 py-16 text-center">
          <p className="text-slate-400">No datasets yet.</p>
          <Link to="/datasets/upload" className="mt-2 inline-block text-sm font-medium text-brand-400 hover:text-brand-300">
            Upload your first one →
          </Link>
        </div>
      )}

      {datasets && datasets.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {datasets.map((d) => (
            <Link
              key={d.id}
              to={`/datasets/${d.id}`}
              className="rounded-xl border border-border bg-surface p-5 transition-colors hover:border-slate-600 hover:bg-surface-hover"
            >
              <p className="truncate font-medium text-slate-100">{d.filename}</p>
              {d.sheet_name && <p className="mt-0.5 text-xs text-slate-500">Sheet: {d.sheet_name}</p>}
              <div className="mt-3 flex gap-4 text-sm text-slate-400">
                <span>{d.rows.toLocaleString('en-US')} rows</span>
                <span>{d.columns} columns</span>
              </div>
              <p className="mt-3 text-xs text-slate-600">
                Uploaded {new Date(d.uploaded_at).toLocaleDateString()}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
