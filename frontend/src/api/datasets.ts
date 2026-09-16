import { apiClient } from './client'
import type { Dataset, DatasetSummary, UploadResponse } from '../types/api'

export async function listDatasets(): Promise<Dataset[]> {
  const { data } = await apiClient.get<{ datasets: Dataset[] }>('/datasets/')
  return data.datasets
}

export async function getDatasetSummary(id: number): Promise<DatasetSummary> {
  const { data } = await apiClient.get<DatasetSummary>(`/datasets/${id}/summary`)
  return data
}

export async function uploadDataset(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)

  const { data } = await apiClient.post<UploadResponse>('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (onProgress && event.total) {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    },
  })
  return data
}
