import { forwardRef } from 'react'
import { cn } from '../../lib/cn'

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  hint?: string
  mono?: boolean
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, hint, mono, className, id, ...props }, ref) => {
    const inputId = id ?? label?.toLowerCase().replace(/\s+/g, '-')
    return (
      <div className="flex flex-col gap-1">
        {label && (
          <label htmlFor={inputId} className="text-sm font-medium text-gray-700">
            {label}
            {props.required && <span className="ml-1 text-red-500">*</span>}
          </label>
        )}
        {hint && <p className="text-xs text-gray-500">{hint}</p>}
        <input
          ref={ref}
          id={inputId}
          className={cn(
            'rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm placeholder:text-gray-400',
            'focus:border-orange-400 focus:outline-none focus:ring-2 focus:ring-orange-200',
            'disabled:bg-gray-50 disabled:text-gray-500',
            error && 'border-red-400 focus:border-red-400 focus:ring-red-200',
            mono && 'font-mono',
            className,
          )}
          {...props}
        />
        {error && <p className="text-xs text-red-500">{error}</p>}
      </div>
    )
  },
)
Input.displayName = 'Input'
