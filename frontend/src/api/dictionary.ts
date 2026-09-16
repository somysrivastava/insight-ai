import { apiClient } from './client'
import type { ColumnMapping } from '../types/api'

export async function getDictionary(datasetId: number): Promise<ColumnMapping[]> {
  const { data } = await apiClient.get<ColumnMapping[]>(`/datasets/${datasetId}/dictionary`)
  return data
}
