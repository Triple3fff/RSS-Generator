import { useState } from 'react'
import { HelpCircle } from 'lucide-react'
import { cn } from '../../lib/cn'

interface TooltipProps {
  content: string
  className?: string
}

export function Tooltip({ content, className }: TooltipProps) {
  const [visible, setVisible] = useState(false)

  return (
    <span
      className={cn('relative inline-flex', className)}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      <HelpCircle className="h-3.5 w-3.5 cursor-help text-gray-400 hover:text-gray-600" />
      {visible && (
        <span className="absolute bottom-full left-1/2 z-10 mb-1.5 w-56 -translate-x-1/2 rounded-md bg-gray-800 px-2.5 py-1.5 text-xs text-white shadow-lg">
          {content}
          <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-800" />
        </span>
      )}
    </span>
  )
}
