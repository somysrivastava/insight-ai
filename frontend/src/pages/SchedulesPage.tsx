import { useState } from 'react'
import { useDatasets } from '../hooks/useDatasets'
import { useCreateSchedule, useDeleteSchedule, useRunScheduleNow, useSchedules } from '../hooks/useSchedules'
import { getErrorMessage } from '../api/client'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { ErrorBanner } from '../components/ErrorBanner'
import type { ExportFormat, ScheduledReport, ScheduleFrequency, ScheduleSourceType } from '../types/api'

const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

export function SchedulesPage() {
  const { data: schedules, isLoading, isError, error: listError } = useSchedules()
  const { data: datasets } = useDatasets()
  const [showForm, setShowForm] = useState(false)

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Scheduled reports</h1>
          <p className="mt-1 text-sm text-slate-500">Recurring exports emailed to anyone, on a schedule.</p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-500"
        >
          {showForm ? 'Cancel' : 'New schedule'}
        </button>
      </div>

      {showForm && <CreateScheduleForm datasets={datasets ?? []} onDone={() => setShowForm(false)} />}

      {isLoading && <LoadingSpinner label="Loading schedules…" />}
      {isError && <ErrorBanner message={getErrorMessage(listError)} />}

      {schedules && schedules.length === 0 && !showForm && (
        <div className="rounded-xl border border-dashed border-border px-6 py-16 text-center">
          <p className="text-slate-400">No scheduled reports yet.</p>
        </div>
      )}

      {schedules && schedules.length > 0 && (
        <div className="mt-2 overflow-hidden rounded-xl border border-border">
          <table className="w-full text-left text-sm">
            <thead className="bg-surface-hover text-xs uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">What</th>
                <th className="px-4 py-3 font-medium">Frequency</th>
                <th className="px-4 py-3 font-medium">Recipients</th>
                <th className="px-4 py-3 font-medium">Next run</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border bg-surface">
              {schedules.map((s) => (
                <ScheduleRow key={s.id} schedule={s} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function ScheduleRow({ schedule }: { schedule: ScheduledReport }) {
  const deleteSchedule = useDeleteSchedule()
  const runNow = useRunScheduleNow()
  const [message, setMessage] = useState<string | null>(null)

  function handleRunNow() {
    setMessage(null)
    runNow.mutate(schedule.id, {
      onSuccess: (job) => setMessage(job.status === 'success' ? 'Sent.' : job.error || 'Failed.'),
      onError: (err) => setMessage(getErrorMessage(err)),
    })
  }

  const whatLabel =
    schedule.source_type === 'report'
      ? 'Full report'
      : schedule.question
        ? `"${schedule.question}"`
        : schedule.source_type

  return (
    <tr>
      <td className="px-4 py-3 text-slate-200">{schedule.name}</td>
      <td className="max-w-xs truncate px-4 py-3 text-slate-400">{whatLabel}</td>
      <td className="px-4 py-3 text-slate-400">
        {schedule.frequency}
        {schedule.frequency === 'weekly' && schedule.day_of_week !== null && ` (${DAY_NAMES[schedule.day_of_week]})`}
        {schedule.frequency === 'monthly' && schedule.day_of_month !== null && ` (day ${schedule.day_of_month})`}
        {' @ '}
        {String(schedule.hour).padStart(2, '0')}:00 UTC
      </td>
      <td className="px-4 py-3 text-slate-400">{schedule.recipients.join(', ')}</td>
      <td className="px-4 py-3 text-slate-400">{new Date(schedule.next_run_at).toLocaleString()}</td>
      <td className="px-4 py-3">
        <div className="flex items-center justify-end gap-2">
          {message && <span className="text-xs text-slate-500">{message}</span>}
          <button
            onClick={handleRunNow}
            disabled={runNow.isPending}
            className="rounded-md border border-border px-2.5 py-1 text-xs font-medium text-slate-300 hover:bg-surface-hover disabled:opacity-60"
          >
            {runNow.isPending ? '…' : 'Run now'}
          </button>
          <button
            onClick={() => deleteSchedule.mutate(schedule.id)}
            className="rounded-md border border-border px-2.5 py-1 text-xs font-medium text-slate-300 hover:bg-red-950/40 hover:text-red-300"
          >
            Delete
          </button>
        </div>
      </td>
    </tr>
  )
}

function CreateScheduleForm({
  datasets,
  onDone,
}: {
  datasets: { id: number; filename: string; sheet_name: string | null }[]
  onDone: () => void
}) {
  const [name, setName] = useState('')
  const [sourceType, setSourceType] = useState<ScheduleSourceType>('report')
  const [datasetId, setDatasetId] = useState<number | ''>('')
  const [question, setQuestion] = useState('')
  const [format, setFormat] = useState<ExportFormat>('pdf')
  const [frequency, setFrequency] = useState<ScheduleFrequency>('daily')
  const [dayOfWeek, setDayOfWeek] = useState(1)
  const [dayOfMonth, setDayOfMonth] = useState(1)
  const [hour, setHour] = useState(9)
  const [recipients, setRecipients] = useState('')
  const create = useCreateSchedule()

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!datasetId || !name.trim() || !recipients.trim()) return
    if (sourceType === 'dataset_query' && !question.trim()) return

    create.mutate(
      {
        name: name.trim(),
        source_type: sourceType,
        source_id: datasetId,
        question: sourceType === 'dataset_query' ? question.trim() : undefined,
        export_format: format,
        frequency,
        day_of_week: frequency === 'weekly' ? dayOfWeek : undefined,
        day_of_month: frequency === 'monthly' ? dayOfMonth : undefined,
        hour,
        recipients: recipients.split(',').map((r) => r.trim()).filter(Boolean),
      },
      { onSuccess: onDone },
    )
  }

  return (
    <form onSubmit={handleSubmit} className="mb-6 space-y-4 rounded-xl border border-border bg-surface p-5">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-300">Name</label>
          <input
            required
            name="schedule-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-100 outline-none focus:border-brand-500"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-300">Dataset</label>
          <select
            required
            name="schedule-dataset"
            value={datasetId}
            onChange={(e) => setDatasetId(Number(e.target.value))}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-100 outline-none focus:border-brand-500"
          >
            <option value="" disabled>
              Select a dataset…
            </option>
            {datasets.map((d) => (
              <option key={d.id} value={d.id}>
                {d.filename}
                {d.sheet_name ? ` — ${d.sheet_name}` : ''}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <label className="mb-1.5 block text-sm font-medium text-slate-300">What to send</label>
        <div className="flex gap-2">
          {(['report', 'dataset_query'] as ScheduleSourceType[]).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setSourceType(t)}
              className={`flex-1 rounded-lg border px-3 py-2 text-sm font-medium ${
                sourceType === t
                  ? 'border-brand-500 bg-brand-600/15 text-brand-300'
                  : 'border-border text-slate-400 hover:bg-surface-hover'
              }`}
            >
              {t === 'report' ? 'Full Report' : 'Specific Question'}
            </button>
          ))}
        </div>
      </div>

      {sourceType === 'dataset_query' && (
        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-300">Question</label>
          <input
            required
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. What was total revenue this week?"
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-100 outline-none focus:border-brand-500"
          />
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-300">Frequency</label>
          <select
            value={frequency}
            onChange={(e) => setFrequency(e.target.value as ScheduleFrequency)}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-100 outline-none focus:border-brand-500"
          >
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </div>

        {frequency === 'weekly' && (
          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-300">Day of week</label>
            <select
              value={dayOfWeek}
              onChange={(e) => setDayOfWeek(Number(e.target.value))}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-100 outline-none focus:border-brand-500"
            >
              {DAY_NAMES.map((d, i) => (
                <option key={d} value={i}>
                  {d}
                </option>
              ))}
            </select>
          </div>
        )}

        {frequency === 'monthly' && (
          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-300">Day of month</label>
            <input
              type="number"
              min={1}
              max={31}
              value={dayOfMonth}
              onChange={(e) => setDayOfMonth(Number(e.target.value))}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-100 outline-none focus:border-brand-500"
            />
          </div>
        )}

        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-300">Hour (UTC)</label>
          <input
            type="number"
            min={0}
            max={23}
            value={hour}
            onChange={(e) => setHour(Number(e.target.value))}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-100 outline-none focus:border-brand-500"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-300">Format</label>
          <div className="flex gap-2">
            {(['csv', 'xlsx', 'pdf'] as ExportFormat[]).map((f) => (
              <button
                key={f}
                type="button"
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
        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-300">Recipients (comma-separated)</label>
          <input
            required
            value={recipients}
            onChange={(e) => setRecipients(e.target.value)}
            placeholder="you@example.com, team@example.com"
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-slate-100 outline-none focus:border-brand-500"
          />
        </div>
      </div>

      {!!create.error && <ErrorBanner message={getErrorMessage(create.error)} />}

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={create.isPending}
          className="flex items-center gap-2 rounded-lg bg-brand-600 px-5 py-2 text-sm font-medium text-white hover:bg-brand-500 disabled:opacity-60"
        >
          {create.isPending ? <LoadingSpinner size="sm" /> : 'Create schedule'}
        </button>
      </div>
    </form>
  )
}
