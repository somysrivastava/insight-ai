import { apiClient } from './client'
import type { JobResponse } from '../types/api'

export async function getJob(taskId: string): Promise<JobResponse> {
  const { data } = await apiClient.get<JobResponse>(`/jobs/${taskId}`)
  return data
}

/**
 * Polls GET /jobs/{task_id} until it leaves "pending" — every async
 * endpoint in this API (exports, dashboard refresh, AI query async)
 * shares this one polling surface, so one helper covers all of them.
 */
export async function pollJob(
  taskId: string,
  { intervalMs = 1000, timeoutMs = 60000 }: { intervalMs?: number; timeoutMs?: number } = {},
): Promise<JobResponse> {
  const start = Date.now()
  while (true) {
    const job = await getJob(taskId)
    if (job.status !== 'pending') return job
    if (Date.now() - start > timeoutMs) {
      throw new Error('Timed out waiting for the job to complete.')
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs))
  }
}
