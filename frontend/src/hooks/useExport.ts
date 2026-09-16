import { useMutation } from '@tanstack/react-query'
import { downloadExport, submitExport } from '../api/exports'
import { pollJob } from '../api/jobs'
import type { ExportFormat, ExportSource } from '../types/api'

interface ExportArgs {
  source: ExportSource
  format: ExportFormat
  question?: string
  group_by?: string
  filename: string
}

/** Submits the export, polls to completion, then downloads the file — one mutation covers the whole flow for the UI. */
export function useExportDataset(datasetId: number) {
  return useMutation({
    mutationFn: async ({ source, format, question, group_by, filename }: ExportArgs) => {
      const { task_id } = await submitExport(datasetId, source, format, { question, group_by })
      const job = await pollJob(task_id, { timeoutMs: 60000 })
      if (job.status === 'failed' || !job.result) {
        throw new Error(job.error || 'Export failed.')
      }
      const result = job.result as { export_id: number; status: string; error: string | null }
      if (result.status !== 'success') {
        throw new Error(result.error || 'Export failed.')
      }
      await downloadExport(result.export_id, `${filename}.${format}`)
    },
  })
}
