import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createSchedule, deleteSchedule, listSchedules, runScheduleNow } from '../api/schedules'
import { pollJob } from '../api/jobs'
import type { CreateScheduleRequest } from '../types/api'

export function useSchedules() {
  return useQuery({ queryKey: ['schedules'], queryFn: listSchedules })
}

export function useCreateSchedule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: CreateScheduleRequest) => createSchedule(request),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['schedules'] }),
  })
}

export function useDeleteSchedule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteSchedule(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['schedules'] }),
  })
}

export function useRunScheduleNow() {
  return useMutation({
    mutationFn: async (id: number) => {
      const { task_id } = await runScheduleNow(id)
      return pollJob(task_id, { timeoutMs: 60000 })
    },
  })
}
