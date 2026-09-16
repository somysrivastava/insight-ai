import { apiClient } from './client'
import type { CreateScheduleRequest, JobSubmitResponse, ScheduledReport } from '../types/api'

export async function listSchedules(): Promise<ScheduledReport[]> {
  const { data } = await apiClient.get<ScheduledReport[]>('/schedules')
  return data
}

export async function createSchedule(request: CreateScheduleRequest): Promise<ScheduledReport> {
  const { data } = await apiClient.post<ScheduledReport>('/schedules', request)
  return data
}

export async function deleteSchedule(id: number): Promise<void> {
  await apiClient.delete(`/schedules/${id}`)
}

export async function runScheduleNow(id: number): Promise<JobSubmitResponse> {
  const { data } = await apiClient.post<JobSubmitResponse>(`/schedules/${id}/run`)
  return data
}
