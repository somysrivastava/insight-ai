import { useCallback, useRef, useState } from 'react'

interface Props {
  onFileSelected: (file: File) => void
  disabled?: boolean
  progress?: number
}

const ACCEPTED = '.csv,.xlsx,.xls'

export function UploadDropzone({ onFileSelected, disabled, progress = 0 }: Props) {
  const [isDragOver, setIsDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      setIsDragOver(false)
      if (disabled) return
      const file = e.dataTransfer.files?.[0]
      if (file) onFileSelected(file)
    },
    [disabled, onFileSelected],
  )

  const isUploading = progress > 0 && progress < 100

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        if (!disabled) setIsDragOver(true)
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={handleDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-16 text-center transition-colors ${
        isDragOver ? 'border-brand-500 bg-brand-500/5' : 'border-border bg-surface hover:border-slate-600'
      } ${disabled ? 'pointer-events-none opacity-60' : ''}`}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) onFileSelected(file)
          e.target.value = ''
        }}
      />

      {isUploading ? (
        <div className="w-full max-w-xs">
          <div className="mb-2 text-sm text-slate-300">Uploading… {progress}%</div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-border">
            <div
              className="h-full rounded-full bg-brand-500 transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      ) : (
        <>
          <svg
            className="h-10 w-10 text-slate-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
          </svg>
          <div>
            <p className="font-medium text-slate-200">Drag and drop a CSV or Excel file</p>
            <p className="mt-1 text-sm text-slate-500">or click to browse</p>
          </div>
        </>
      )}
    </div>
  )
}
