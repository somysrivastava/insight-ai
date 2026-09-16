import { useNavigate } from 'react-router-dom'
import { useUploadDataset } from '../hooks/useDatasets'
import { getErrorMessage } from '../api/client'
import { UploadDropzone } from '../components/UploadDropzone'
import { ErrorBanner } from '../components/ErrorBanner'

export function UploadPage() {
  const navigate = useNavigate()
  const { mutate, isPending, progress, error } = useUploadDataset()

  function handleFile(file: File) {
    mutate(file, {
      onSuccess: (response) => {
        if ('dataset' in response) {
          navigate(`/datasets/${response.dataset.id}`)
        } else {
          // Multi-sheet Excel — one dataset per sheet, no single page to land on.
          navigate('/datasets')
        }
      },
    })
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-semibold text-white">Upload a dataset</h1>
      <p className="mt-1 text-sm text-slate-500">CSV or Excel. A multi-sheet Excel file creates one dataset per sheet.</p>

      <div className="mt-6">
        {!!error && <div className="mb-4"><ErrorBanner message={getErrorMessage(error)} /></div>}
        <UploadDropzone onFileSelected={handleFile} disabled={isPending} progress={progress} />
      </div>
    </div>
  )
}
