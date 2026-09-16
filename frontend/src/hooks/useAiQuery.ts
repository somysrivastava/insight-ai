import { useMutation } from '@tanstack/react-query'
import { askQuestion } from '../api/ai'

export function useAskQuestion(datasetId: number) {
  return useMutation({
    mutationFn: (question: string) => askQuestion(datasetId, question),
  })
}
