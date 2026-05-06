import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { supabase } from '../lib/supabaseClient.js'
import {
  Zap, Mail, Lock, AlertCircle, Loader2,
  Linkedin, ArrowUpRight, Clock,
} from 'lucide-react'

/**
 * AuthPage — minimal light two-pane landing.
 * Left: short pitch + author. Right: auth form.
 *
 * Props:
 *   onLogin(user, accessToken) — fired on successful auth.
 */
export default function AuthPage({ onLogin }) {
  const [mode, setMode]         = useState('login')
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)
  const [info, setInfo]         = useState(null)

  const isLogin  = mode === 'login'
  const btnLabel = isLogin ? 'Sign in' : 'Create account'

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setInfo(null)

    if (!email.trim() || !password) {
      setError('Please enter your email and password.')
      return
    }
    if (!isLogin && password.length < 6) {
      setError('Password must be at least 6 characters.')
      return
    }

    setLoading(true)
    try {
      if (isLogin) {
        const { data, error: sbErr } = await supabase.auth.signInWithPassword({
          email: email.trim(),
          password,
        })
        if (sbErr) throw sbErr
        if (data?.user) onLogin(data.user, data.session?.access_token ?? null)
      } else {
        const { data, error: sbErr } = await supabase.auth.signUp({
          email: email.trim(),
          password,
        })
        if (sbErr) throw sbErr
        if (data?.user?.identities?.length === 0) {
          setInfo('An account with this email already exists. Try signing in.')
        } else if (data?.session) {
          onLogin(data.user, data.session?.access_token ?? null)
        } else {
          setInfo('Account created. Check your email to confirm, then sign in.')
          setMode('login')
        }
      }
    } catch (err) {
      setError(err.message ?? 'Authentication failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const fade = {
    hidden: { opacity: 0, y: 12 },
    show:   (i = 0) => ({
      opacity: 1, y: 0,
      transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1], delay: 0.05 + i * 0.07 },
    }),
  }

  return (
    <div className="min-h-screen flex bg-[#fafaf9] text-gray-900 font-sans">

      {/* ──────────────── LEFT PANE ──────────────── */}
      <aside
        className="
          relative hidden lg:flex flex-col justify-between
          w-1/2 px-16 xl:px-24 py-14
        "
      >
        {/* soft accent */}
        <div
          aria-hidden
          className="absolute top-0 left-0 w-[24rem] h-[24rem] bg-primary/[0.06] rounded-full blur-[100px] -z-0"
        />

        {/* Brand */}
        <motion.div
          custom={0}
          initial="hidden"
          animate="show"
          variants={fade}
          className="flex items-center gap-2.5 relative"
        >
          <div className="w-9 h-9 rounded-lg bg-primary flex items-center justify-center">
            <Zap size={16} className="text-white" />
          </div>
          <span className="font-semibold text-[15px] tracking-tight">Omega TK</span>
        </motion.div>

        {/* Pitch */}
        <div className="relative max-w-md">
          <motion.h1
            custom={1}
            initial="hidden"
            animate="show"
            variants={fade}
            className="text-[2.5rem] xl:text-[2.75rem] font-semibold leading-[1.1] tracking-tight text-gray-900"
          >
            Omega Toolkit code,
            <br />
            <span className="text-primary">on demand.</span>
          </motion.h1>

          <motion.p
            custom={2}
            initial="hidden"
            animate="show"
            variants={fade}
            className="mt-5 text-[14px] leading-relaxed text-gray-500 max-w-sm"
          >
            A retrieval grounded assistant for the OpenEye Omega Toolkit.
            Ask in English, get cited Python.
          </motion.p>

          <motion.div
            custom={3}
            initial="hidden"
            animate="show"
            variants={fade}
            className="flex flex-wrap gap-2 mt-6"
          >
            {['RAG', 'FAISS', 'GPT 4o mini', 'Guardrails'].map(t => (
              <span
                key={t}
                className="
                  px-2.5 py-1 rounded-full
                  bg-white border border-gray-200
                  text-[11px] text-gray-600
                "
              >
                {t}
              </span>
            ))}
          </motion.div>

          {/* Cold start note */}
          <motion.div
            custom={4}
            initial="hidden"
            animate="show"
            variants={fade}
            className="mt-8 flex items-start gap-2.5 text-[12px] text-gray-500 leading-relaxed max-w-sm"
          >
            <Clock size={13} className="text-amber-500 mt-0.5 flex-shrink-0" />
            <span>
              First request may take 30 to 60 seconds. Hosted on free tier infrastructure that cold starts after idle.
            </span>
          </motion.div>
        </div>

        {/* Author */}
        <motion.div
          custom={5}
          initial="hidden"
          animate="show"
          variants={fade}
          className="relative"
        >
          <p className="text-[10px] uppercase tracking-[0.16em] text-gray-400 mb-3">
            Built by
          </p>
          <div className="flex items-center gap-3">
            <div
              className="
                w-10 h-10 rounded-full flex-shrink-0
                bg-gradient-to-br from-primary to-violet-400
                flex items-center justify-center
                font-medium text-white text-[13px]
              "
            >
              IS
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-medium text-[13.5px] text-gray-900 leading-tight">Ishan Srivastava</p>
              <p className="text-[11.5px] text-gray-500 mt-0.5">M.S. Applied AI, Northeastern</p>
            </div>
            <div className="flex items-center gap-1.5">
              <a
                href="https://www.linkedin.com/in/ishan-srivastava-7742b121a/"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="LinkedIn"
                className="
                  w-8 h-8 rounded-lg flex items-center justify-center
                  bg-white border border-gray-200 text-gray-500
                  hover:text-primary hover:border-primary/30 hover:bg-primary/[0.04]
                  transition-colors
                "
              >
                <Linkedin size={13} />
              </a>
              <a
                href="mailto:srivastava.ish@northeastern.edu"
                aria-label="Email"
                className="
                  w-8 h-8 rounded-lg flex items-center justify-center
                  bg-white border border-gray-200 text-gray-500
                  hover:text-primary hover:border-primary/30 hover:bg-primary/[0.04]
                  transition-colors
                "
              >
                <Mail size={13} />
              </a>
            </div>
          </div>
        </motion.div>
      </aside>

      {/* divider */}
      <div className="hidden lg:block w-px bg-gray-200" />

      {/* ──────────────── RIGHT PANE ──────────────── */}
      <main className="flex-1 flex items-center justify-center px-6 sm:px-10 py-12 bg-white">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1], delay: 0.15 }}
          className="w-full max-w-[360px]"
        >
          {/* Mobile brand */}
          <div className="lg:hidden flex flex-col items-center mb-10">
            <div className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center mb-3">
              <Zap size={18} className="text-white" />
            </div>
            <h1 className="font-semibold text-[15px] tracking-tight">Omega TK</h1>
          </div>

          {/* Header */}
          <AnimatePresence mode="wait">
            <motion.div
              key={mode}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.22 }}
              className="mb-8"
            >
              <h2 className="text-[22px] font-semibold tracking-tight text-gray-900">
                {isLogin ? 'Welcome back' : 'Create account'}
              </h2>
              <p className="text-[12.5px] text-gray-500 mt-1.5">
                {isLogin
                  ? 'Sign in to continue.'
                  : 'A free account to save your sessions.'}
              </p>
            </motion.div>
          </AnimatePresence>

          {/* Banners */}
          <AnimatePresence>
            {error && (
              <motion.div
                key="err"
                initial={{ opacity: 0, height: 0, marginBottom: 0 }}
                animate={{ opacity: 1, height: 'auto', marginBottom: 16 }}
                exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden"
              >
                <div className="flex items-start gap-2 bg-red-50 border border-red-100 rounded-lg px-3 py-2.5 text-[12px] text-red-700">
                  <AlertCircle size={13} className="flex-shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              </motion.div>
            )}
            {info && (
              <motion.div
                key="info"
                initial={{ opacity: 0, height: 0, marginBottom: 0 }}
                animate={{ opacity: 1, height: 'auto', marginBottom: 16 }}
                exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden"
              >
                <div className="flex items-start gap-2 bg-emerald-50 border border-emerald-100 rounded-lg px-3 py-2.5 text-[12px] text-emerald-700">
                  <span>{info}</span>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <form onSubmit={handleSubmit} className="space-y-3">
            {/* Email */}
            <div>
              <label className="block text-[11px] font-medium text-gray-600 mb-1.5">Email</label>
              <div className="relative">
                <Mail size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-300 pointer-events-none" />
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  autoComplete="email"
                  required
                  className="
                    w-full bg-white border border-gray-200 rounded-lg pl-9 pr-3 py-2.5
                    text-[13px] text-gray-900 placeholder-gray-300
                    outline-none focus:border-primary focus:ring-2 focus:ring-primary/15
                    transition-all
                  "
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label className="block text-[11px] font-medium text-gray-600 mb-1.5">Password</label>
              <div className="relative">
                <Lock size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-300 pointer-events-none" />
                <input
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder={isLogin ? '••••••••' : 'At least 6 characters'}
                  autoComplete={isLogin ? 'current-password' : 'new-password'}
                  required
                  className="
                    w-full bg-white border border-gray-200 rounded-lg pl-9 pr-3 py-2.5
                    text-[13px] text-gray-900 placeholder-gray-300
                    outline-none focus:border-primary focus:ring-2 focus:ring-primary/15
                    transition-all
                  "
                />
              </div>
            </div>

            {/* Submit */}
            <motion.button
              type="submit"
              disabled={loading}
              whileTap={{ scale: loading ? 1 : 0.985 }}
              className="
                w-full flex items-center justify-center gap-2
                py-2.5 mt-5 rounded-lg
                bg-gray-900 hover:bg-black
                text-white text-[13px] font-medium
                transition-colors disabled:opacity-50 disabled:cursor-not-allowed
              "
            >
              {loading
                ? <><Loader2 size={13} className="animate-spin" /> {isLogin ? 'Signing in' : 'Creating'}</>
                : <>{btnLabel} <ArrowUpRight size={13} className="opacity-70" /></>}
            </motion.button>
          </form>

          {/* Toggle */}
          <p className="text-center text-gray-500 text-[12px] mt-6">
            {isLogin ? 'New here? ' : 'Have an account? '}
            <button
              onClick={() => { setMode(isLogin ? 'signup' : 'login'); setError(null); setInfo(null) }}
              className="text-primary hover:text-primary-dark font-medium transition-colors"
            >
              {isLogin ? 'Create an account' : 'Sign in'}
            </button>
          </p>

          {/* Mobile cold start */}
          <div className="lg:hidden mt-8 flex items-start gap-2 text-[11px] text-gray-500 leading-relaxed">
            <Clock size={12} className="text-amber-500 mt-0.5 flex-shrink-0" />
            <span>First request may take 30 to 60 seconds. Free tier cold start.</span>
          </div>
        </motion.div>
      </main>
    </div>
  )
}
