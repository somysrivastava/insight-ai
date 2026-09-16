import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { getDatasetSummary, listDatasets, uploadDataset } from '../api/datasets'
import { getDictionary } from '../api/dictionary'
import type { UploadResponse } from '../types/api'

export function useDatasets() {
  return useQuery({ queryKey: ['datasets'], queryFn: listDatasets })
}

export function useDatasetSummary(id: number | undefined) {
  return useQuery({
    queryKey: ['datasets', id, 'summary'],
    queryFn: () => getDatasetSummary(id as number),
    enabled: id !== undefined,
  })
}

export function useDictionary(id: number | undefined) {
  return useQuery({
    queryKey: ['datasets', id, 'dictionary'],
    queryFn: () => getDictionary(id as number),
    enabled: id !== undefined,
  })
}

export function useUploadDataset() {
  const queryClient = useQueryClient()
  const [progress, setProgress] = useState(0)

  const mutation = useMutation<UploadResponse, unknown, File>({
    mutationFn: (file: File) => uploadDataset(file, setProgress),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] })
    },
    onSettled: () => setProgress(0),
  })

  return { ...mutation, progress }
}
