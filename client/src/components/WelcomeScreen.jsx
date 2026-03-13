/**
 * Welcome content displayed inside the message area before the first message.
 * Centered vertically. No InputBar — that lives in App.jsx.
 * Clean ChatGPT-style: no gradients, no blobs, no glassmorphism.
 */
import { motion } from 'framer-motion'

const SUGGESTIONS = [
  'Generate conformers for a single molecule',
  'Loop conformer generation over a database',
  'Enumerate stereochemistry with Flipper',
  'Handle Omega return codes and errors',
]

/** @param {{ onSend: (text: string) => void }} props */
export default function WelcomeScreen({ onSend }) {
  return (
    <div className="flex flex-col items-center justify-center h-full px-4 pb-8">
      <div className="w-full max-w-3xl">

        {/* ── Heading ── */}
        <motion.div
          className="text-center mb-10"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
        >
          <h1 className="text-3xl font-semibold mb-3 text-[#ececec]">
            Omega TK Code Assistant
          </h1>
          <p className="text-[#9b9b9b] text-base">
            Your AI-powered guide to OpenEye conformer generation
          </p>
        </motion.div>

        {/* ── Suggestion cards ── */}
        <div className="grid grid-cols-2 gap-3 mb-6">
          {SUGGESTIONS.map((suggestion, i) => (
            <motion.button
              key={suggestion}
              onClick={() => onSend(suggestion)}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: 0.1 + i * 0.06, ease: 'easeOut' }}
              className="bg-[#2f2f2f] hover:bg-[#3a3a3a] border border-[#424242] rounded-xl p-4 text-left text-sm text-[#ececec] transition-colors duration-150 cursor-pointer leading-snug"
            >
              {suggestion}
            </motion.button>
          ))}
        </div>

        {/* ── Bottom branding ── */}
        <motion.p
          className="text-center text-xs text-[#666]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.4 }}
        >
          Built for OpenEye Omega Toolkit
        </motion.p>
      </div>
    </div>
  )
}
