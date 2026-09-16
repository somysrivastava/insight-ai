import { apiClient } from './client'
import type { ExportFormat, ExportSource, JobSubmitResponse } from '../types/api'

export async function submitExport(
  datasetId: number,
  source: ExportSource,
  format: ExportFormat,
  options: { question?: string; group_by?: string } = {},
): Promise<JobSubmitResponse> {
  const { data } = await apiClient.post<JobSubmitResponse>(`/datasets/${datasetId}/export`, {
    source,
    format,
    question: options.question,
    group_by: options.group_by,
  })
  return data
}

/**
 * GET /exports/{id} streams the file and requires the same JWT every
 * other endpoint does — a plain <a href> download can't attach an
 * Authorization header, so this fetches the bytes via axios (with the
 * interceptor-attached token) as a blob, then triggers the browser's
 * save dialog from an in-memory object URL. Revokes the object URL
 * right after — it's only needed for the instant the click fires.
 */
export async function downloadExport(exportId: number, filename: string): Promise<void> {
  const response = await apiClient.get(`/exports/${exportId}`, { responseType: 'blob' })
  const url = window.URL.createObjectURL(new Blob([response.data]))
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', filename)
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}
