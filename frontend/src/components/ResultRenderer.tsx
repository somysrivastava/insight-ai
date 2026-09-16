import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { StructuredQueryResult } from '../types/api'

interface Props {
  data: StructuredQueryResult
}

// Pinned to 'en-US' deliberately, not the browser's own locale
// (`undefined`) — a browser set to e.g. en-IN groups digits in
// lakhs/crores (3,96,72,031.43), which reads as a bug to anyone
// expecting standard international grouping (39,672,031.43). This app
// has no locale switcher, so one fixed, predictable format is correct
// everywhere it's used, not just here.
function formatCellValue(value: unknown): string {
  if (typeof value === 'number') return value.toLocaleString('en-US', { maximumFractionDigits: 2 })
  if (value === null || value === undefined) return '—'
  return String(value)
}

// Recharts' default YAxis tick prints the raw number — fine for small
// values, unreadable once bars are in the millions (a repeating run of
// zeros). Abbreviates the same way spreadsheet tools do.
function formatAxisNumber(value: number): string {
  const abs = Math.abs(value)
  if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (abs >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return String(value)
}

/** Picks the first string-valued key as the chart's category axis and the first numeric key as the bar value — matches the shape execute_structured_query's groupby/sort/filter operations actually produce (one category column, one metric column). */
function pickChartKeys(records: Record<string, unknown>[]): { categoryKey: string; valueKey: string } | null {
  if (records.length === 0) return null
  const sample = records[0]
  const categoryKey = Object.keys(sample).find((k) => typeof sample[k] === 'string')
  const valueKey = Object.keys(sample).find((k) => typeof sample[k] === 'number')
  if (!categoryKey || !valueKey) return null
  return { categoryKey, valueKey }
}

/**
 * The AI query response's `data` shape varies by operation
 * (groupby/sort/filter return `records`; aggregate/correlate return a
 * single value) — this never forces a chart onto a shape that doesn't
 * have one. Reused by both Flow 1 (the query interface) and Flow 2
 * (dashboard pin cards), since a dataset_query pin's cached_result.data
 * is this exact same shape.
 */
export function ResultRenderer({ data }: Props) {
  const records = data.records

  if (records && records.length > 0) {
    const chartKeys = pickChartKeys(records)
    const columns = Object.keys(records[0])

    return (
      <div className="space-y-4">
        {chartKeys && (
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={records} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#232838" />
                <XAxis
                  dataKey={chartKeys.categoryKey}
                  tick={{ fill: '#94a3b8', fontSize: 12 }}
                  angle={-20}
                  textAnchor="end"
                  height={50}
                />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} tickFormatter={formatAxisNumber} />
                <Tooltip
                  contentStyle={{ background: '#131722', border: '1px solid #232838', borderRadius: 8 }}
                  labelStyle={{ color: '#e2e8f0' }}
                />
                <Bar dataKey={chartKeys.valueKey} fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        <div className="max-h-64 overflow-auto rounded-lg border border-border">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-surface-hover text-xs uppercase tracking-wide text-slate-400">
              <tr>
                {columns.map((col) => (
                  <th key={col} className="px-3 py-2 font-medium">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {records.map((row, i) => (
                <tr key={i} className="hover:bg-surface-hover">
                  {columns.map((col) => (
                    <td key={col} className="px-3 py-2 text-slate-300">
                      {formatCellValue(row[col])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  if (data.operation === 'correlate') {
    return (
      <div className="rounded-lg border border-border bg-surface-hover px-5 py-6 text-center">
        <div className="text-3xl font-semibold text-brand-300">
          {data.correlation === null || data.correlation === undefined ? '—' : data.correlation.toFixed(3)}
        </div>
        <div className="mt-1 text-sm text-slate-400">
          correlation between {data.column} and {data.metric}
        </div>
      </div>
    )
  }

  if (data.value !== undefined) {
    return (
      <div className="rounded-lg border border-border bg-surface-hover px-5 py-6 text-center">
        <div className="text-3xl font-semibold text-brand-300">{formatCellValue(data.value)}</div>
        <div className="mt-1 text-sm text-slate-400">
          {data.aggregate ?? ''} {data.metric ? `of ${data.metric}` : ''}
        </div>
      </div>
    )
  }

  return <p className="text-sm text-slate-500">No matching records.</p>
}
