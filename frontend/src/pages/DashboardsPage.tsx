import { useEffect, useState } from 'react'
import { useDashboard, useDashboards, useCreateDashboard, useRefreshDashboard } from '../hooks/useDashboards'
import { getErrorMessage } from '../api/client'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { ErrorBanner } from '../components/ErrorBanner'
import { PinCard } from '../components/PinCard'
import { AddPinModal } from '../components/AddPinModal'

export function DashboardsPage() {
  const { data: dashboards, isLoading, isError, error: listError } = useDashboards()
  const [selectedId, setSelectedId] = useState<number | undefined>(undefined)
  const [showAddPin, setShowAddPin] = useState(false)
  const [newName, setNewName] = useState('')
  const createDashboard = useCreateDashboard()

  useEffect(() => {
    if (dashboards && dashboards.length > 0 && selectedId === undefined) {
      setSelectedId(dashboards.find((d) => d.is_default)?.id ?? dashboards[0].id)
    }
  }, [dashboards, selectedId])

  const { data: dashboard, isLoading: dashboardLoading } = useDashboard(selectedId)
  const refreshAll = useRefreshDashboard(selectedId ?? 0)

  if (isLoading) return <LoadingSpinner label="Loading dashboards…" />
  if (isError) return <ErrorBanner message={getErrorMessage(listError)} />

  if (!dashboards || dashboards.length === 0) {
    return (
      <div className="mx-auto max-w-md">
        <h1 className="mb-1 text-2xl font-semibold text-white">Dashboards</h1>
        <p className="mb-6 text-sm text-slate-500">Create a dashboard, then pin results you want to keep an eye on.</p>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (newName.trim()) createDashboard.mutate({ name: newName.trim() })
          }}
          className="flex gap-2 rounded-xl border border-border bg-surface p-4"
        >
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Dashboard name"
            className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-100 outline-none focus:border-brand-500"
          />
          <button
            type="submit"
            disabled={createDashboard.isPending || !newName.trim()}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-500 disabled:opacity-60"
          >
            Create
          </button>
        </form>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <select
            value={selectedId}
            onChange={(e) => setSelectedId(Number(e.target.value))}
            className="rounded-lg border border-border bg-surface px-3 py-2 text-lg font-semibold text-white outline-none focus:border-brand-500"
          >
            {dashboards.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => refreshAll.mutate()}
            disabled={refreshAll.isPending}
            className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium text-slate-200 hover:bg-surface-hover disabled:opacity-60"
          >
            {refreshAll.isPending ? <LoadingSpinner size="sm" /> : 'Refresh all'}
          </button>
          <button
            onClick={() => setShowAddPin(true)}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-500"
          >
            Add pin
          </button>
        </div>
      </div>

      {dashboardLoading && <LoadingSpinner label="Loading pins…" />}

      {dashboard && dashboard.pins.length === 0 && (
        <div className="rounded-xl border border-dashed border-border px-6 py-16 text-center">
          <p className="text-slate-400">No pins yet.</p>
          <button onClick={() => setShowAddPin(true)} className="mt-2 text-sm font-medium text-brand-400 hover:text-brand-300">
            Pin your first result →
          </button>
        </div>
      )}

      {dashboard && dashboard.pins.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {dashboard.pins.map((pin) => (
            <PinCard key={pin.id} dashboardId={dashboard.id} pin={pin} />
          ))}
        </div>
      )}

      {showAddPin && selectedId && <AddPinModal dashboardId={selectedId} onClose={() => setShowAddPin(false)} />}
    </div>
  )
}
