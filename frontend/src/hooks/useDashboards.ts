import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  addPin,
  createDashboard,
  getDashboard,
  listDashboards,
  refreshDashboard,
  refreshPin,
  removePin,
} from '../api/dashboards'
import { pollJob } from '../api/jobs'
import type { PinType } from '../types/api'

export function useDashboards() {
  return useQuery({ queryKey: ['dashboards'], queryFn: listDashboards })
}

export function useDashboard(id: number | undefined) {
  return useQuery({
    queryKey: ['dashboards', id],
    queryFn: () => getDashboard(id as number),
    enabled: id !== undefined,
  })
}

export function useCreateDashboard() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ name, description }: { name: string; description?: string }) =>
      createDashboard(name, description),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['dashboards'] }),
  })
}

export function useAddPin(dashboardId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      title,
      pinType,
      sourceId,
      queryParams,
    }: {
      title: string
      pinType: PinType
      sourceId: number
      queryParams: Record<string, unknown>
    }) => addPin(dashboardId, title, pinType, sourceId, queryParams),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['dashboards', dashboardId] }),
  })
}

export function useRemovePin(dashboardId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (pinId: number) => removePin(dashboardId, pinId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['dashboards', dashboardId] }),
  })
}

/** Fires the refresh, polls the job to completion, then re-fetches the dashboard so the new cached_result shows up. */
export function useRefreshPin(dashboardId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (pinId: number) => {
      const { task_id } = await refreshPin(dashboardId, pinId)
      return pollJob(task_id)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['dashboards', dashboardId] }),
  })
}

export function useRefreshDashboard(dashboardId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { task_id } = await refreshDashboard(dashboardId)
      return pollJob(task_id, { timeoutMs: 120000 })
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['dashboards', dashboardId] }),
  })
}
