import { apiClient } from './client'
import type { Dashboard, DashboardDetail, DashboardPin, JobSubmitResponse, PinType } from '../types/api'

export async function listDashboards(): Promise<Dashboard[]> {
  const { data } = await apiClient.get<Dashboard[]>('/dashboards')
  return data
}

export async function getDashboard(id: number): Promise<DashboardDetail> {
  const { data } = await apiClient.get<DashboardDetail>(`/dashboards/${id}`)
  return data
}

export async function createDashboard(name: string, description?: string): Promise<Dashboard> {
  const { data } = await apiClient.post<Dashboard>('/dashboards', { name, description })
  return data
}

export async function addPin(
  dashboardId: number,
  title: string,
  pinType: PinType,
  sourceId: number,
  queryParams: Record<string, unknown>,
): Promise<DashboardPin> {
  const { data } = await apiClient.post<DashboardPin>(`/dashboards/${dashboardId}/pins`, {
    title,
    pin_type: pinType,
    source_id: sourceId,
    query_params: queryParams,
  })
  return data
}

export async function removePin(dashboardId: number, pinId: number): Promise<void> {
  await apiClient.delete(`/dashboards/${dashboardId}/pins/${pinId}`)
}

export async function refreshPin(dashboardId: number, pinId: number): Promise<JobSubmitResponse> {
  const { data } = await apiClient.post<JobSubmitResponse>(`/dashboards/${dashboardId}/pins/${pinId}/refresh`)
  return data
}

export async function refreshDashboard(dashboardId: number): Promise<JobSubmitResponse> {
  const { data } = await apiClient.post<JobSubmitResponse>(`/dashboards/${dashboardId}/refresh`)
  return data
}
