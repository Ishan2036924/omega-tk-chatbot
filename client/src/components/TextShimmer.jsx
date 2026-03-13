/**
 * TextShimmer — animated gradient text that sweeps left→right continuously.
 * Adapted from 21st.dev reference component (converted from TSX to JSX).
 *
 * Usage:
 *   <TextShimmer duration={1.5}>Thinking...</TextShimmer>
 */
import { useMemo } from 'react'
import { motion } from 'framer-motion'

/**
 * @param {{
 *   children: string,
 *   as?: string,
 *   className?: string,
 *   duration?: number,
 *   spread?: number,
 * }} props
 */
export default function TextShimmer({
  children,
  as: Component = 'span',
  className = '',
  duration = 2,
  spread = 2,
}) {
  const MotionComponent = motion(Component)

  // Spread scales with text length so the sweep looks proportional
  const dynamicSpread = useMemo(() => children.length * spread, [children, spread])

  return (
    <MotionComponent
      className={[
        'relative inline-block bg-[length:250%_100%,auto] bg-clip-text',
        'text-transparent [--base-color:#71717a] [--base-gradient-color:#d4d4d8]',
        '[--bg:linear-gradient(90deg,#0000_calc(50%-var(--spread)),var(--base-gradient-color),#0000_calc(50%+var(--spread)))]',
        '[background-repeat:no-repeat,padding-box]',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      initial={{ backgroundPosition: '100% center' }}
      animate={{ backgroundPosition: '0% center' }}
      transition={{ repeat: Infinity, duration, ease: 'linear' }}
      style={{
        '--spread': `${dynamicSpread}px`,
        backgroundImage: `var(--bg), linear-gradient(var(--base-color), var(--base-color))`,
      }}
    >
      {children}
    </MotionComponent>
  )
}
