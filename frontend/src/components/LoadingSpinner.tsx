interface Props {
  size?: 'sm' | 'md' | 'lg'
  label?: string
}

const sizeClasses = {
  sm: 'h-4 w-4 border-2',
  md: 'h-6 w-6 border-2',
  lg: 'h-10 w-10 border-[3px]',
}

export function LoadingSpinner({ size = 'md', label }: Props) {
  return (
    <div className="flex items-center gap-2 text-slate-400">
      <div
        className={`${sizeClasses[size]} animate-spin rounded-full border-brand-500 border-t-transparent`}
        role="status"
        aria-label={label ?? 'Loading'}
      />
      {label && <span className="text-sm">{label}</span>}
    </div>
  )
}
