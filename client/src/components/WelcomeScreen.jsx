import { motion } from 'framer-motion'
import { Zap, Code2, RefreshCw, GitBranch, AlertCircle } from 'lucide-react'

const SUGGESTIONS = [
  { icon: Code2,      text: 'Generate conformers for a single molecule' },
  { icon: RefreshCw,  text: 'Loop conformer generation over a database' },
  { icon: GitBranch,  text: 'Enumerate stereochemistry with Flipper' },
  { icon: AlertCircle,text: 'Handle Omega return codes and errors' },
]

export default function WelcomeScreen({ onSend }) {
  return (
    <div className="flex flex-col items-center justify-center h-full px-6 pb-8">
      <div className="w-full max-w-2xl">

        {/* Logo + heading */}
        <motion.div
          className="text-center mb-10"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
        >
          <div className="w-12 h-12 rounded-2xl bg-primary mx-auto mb-4 flex items-center justify-center">
            <Zap size={22} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            Omega TK Assistant
          </h1>
          <p className="text-gray-500 text-sm leading-relaxed max-w-sm mx-auto">
            Ask questions, get explanations, and generate code for the OpenEye Omega Toolkit.
          </p>
        </motion.div>

        {/* Suggestion cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {SUGGESTIONS.map(({ icon: Icon, text }, i) => (
            <motion.button
              key={text}
              onClick={() => onSend(text)}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: 0.12 + i * 0.07, ease: 'easeOut' }}
              className="flex items-start gap-3 bg-white border border-gray-200 hover:border-primary/40 hover:bg-primary/5 rounded-xl p-4 text-left transition-all duration-150 group shadow-sm hover:shadow-md"
            >
              <div className="w-7 h-7 rounded-lg bg-gray-100 group-hover:bg-primary/10 flex items-center justify-center flex-shrink-0 mt-0.5 transition-colors">
                <Icon size={14} className="text-gray-500 group-hover:text-primary transition-colors" />
              </div>
              <span className="text-sm text-gray-700 group-hover:text-gray-900 leading-snug transition-colors">
                {text}
              </span>
            </motion.button>
          ))}
        </div>

        {/* Footer */}
        <motion.p
          className="text-center text-xs text-gray-400 mt-8"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.5 }}
        >
          Built for OpenEye Omega Toolkit · Powered by GPT-4o mini
        </motion.p>
      </div>
    </div>
  )
}
