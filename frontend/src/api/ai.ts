import { apiClient } from './client'
import type { QueryResponse } from '../types/api'

export async function askQuestion(datasetId: number, question: string): Promise<QueryResponse> {
  const { data } = await apiClient.post<QueryResponse>(`/datasets/${datasetId}/query`, { question })
  return data
}
