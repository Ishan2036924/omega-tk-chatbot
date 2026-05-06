import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { supabase } from '../lib/supabaseClient.js'
import {
  Zap, Mail, Lock, AlertCircle, Loader2,
  Linkedin, ArrowUpRight, ShieldCheck, Sparkles,
  Database, Cpu, Clock, GraduationCap,
} from 'lucide-react'

/**
 * AuthPage — corporate two-pane landing.
 * Left: app info, cold-start warning, author bio.
 * Right: login / sign-up form.
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
          setInfo('Account created! Check your email to confirm, then sign in.')
          setMode('login')
        }
      }
    } catch (err) {
      setError(err.message ?? 'Authentication failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  // ── Animation variants ──────────────────────────────────────────────────────
  const container = {
    hidden: { opacity: 0 },
    show:   { opacity: 1, transition: { staggerChildren: 0.08, delayChildren: 0.05 } },
  }
  const item = {
    hidden: { opacity: 0, y: 14 },
    show:   { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] } },
  }

  return (
    <div className="min-h-screen flex bg-sidebar text-white overflow-hidden">

      {/* ──────────────── LEFT PANE — info ──────────────── */}
      <motion.aside
        initial="hidden"
        animate="show"
        variants={container}
        className="
          relative hidden lg:flex flex-col justify-between
          w-[52%] xl:w-[55%] px-14 xl:px-20 py-12
          overflow-hidden
        "
      >
        {/* Gradient + grid backdrop */}
        <div className="absolute inset-0 -z-10">
          <div className="absolute inset-0 bg-gradient-to-br from-sidebar via-sidebar-2 to-sidebar-3" />
          <motion.div
            aria-hidden
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 0.55, scale: 1 }}
            transition={{ duration: 1.4, ease: 'easeOut' }}
            className="absolute -top-32 -left-32 w-[28rem] h-[28rem] rounded-full bg-primary/30 blur-[120px]"
          />
          <motion.div
            aria-hidden
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 0.4, scale: 1 }}
            transition={{ duration: 1.6, ease: 'easeOut', delay: 0.2 }}
            className="absolute -bottom-40 -right-20 w-[32rem] h-[32rem] rounded-full bg-sidebar-3/80 blur-[120px]"
          />
          <div
            aria-hidden
            className="absolute inset-0 opacity-[0.04]"
            style={{
              backgroundImage:
                'linear-gradient(to right, #fff 1px, transparent 1px), linear-gradient(to bottom, #fff 1px, transparent 1px)',
              backgroundSize: '38px 38px',
            }}
          />
        </div>

        {/* ── Top: brand ─────────────────────────────────────── */}
        <motion.div variants={item} className="flex items-center gap-3">
          <div className="relative w-11 h-11 rounded-xl bg-primary flex items-center justify-center shadow-lg shadow-primary/30">
            <Zap size={20} className="text-white" />
            <span className="absolute -inset-1 rounded-xl bg-primary/30 blur-md -z-10" />
          </div>
          <div>
            <h1 className="font-semibold text-base tracking-tight leading-tight">Omega TK</h1>
            <p className="text-white/40 text-[11px] -mt-0.5">Code Assistant</p>
          </div>
        </motion.div>

        {/* ── Middle: pitch ──────────────────────────────────── */}
        <div className="max-w-xl">
          <motion.div
            variants={item}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 mb-5
                       rounded-full bg-white/5 border border-white/10 text-[10.5px] tracking-wide uppercase text-white/60"
          >
            <Sparkles size={11} className="text-primary" />
            RAG · OpenEye Omega Toolkit
          </motion.div>

          <motion.h2
            variants={item}
            className="text-3xl xl:text-[2.4rem] font-bold leading-[1.15] tracking-tight"
          >
            Generate working{' '}
            <span className="bg-gradient-to-r from-primary to-violet-300 bg-clip-text text-transparent">
              Omega Toolkit code
            </span>{' '}
            in seconds.
          </motion.h2>

          <motion.p
            variants={item}
            className="mt-4 text-[13.5px] leading-relaxed text-white/55 max-w-md"
          >
            A retrieval-augmented assistant for computational chemists. Ask in plain English,
            get grounded Python — three layers of guardrails keep every answer pinned to the
            official OpenEye documentation.
          </motion.p>

          {/* Feature cards */}
          <motion.div variants={item} className="grid grid-cols-2 gap-3 mt-7 max-w-md">
            {[
              { icon: ShieldCheck, label: 'Three-layer guardrails', sub: 'Intent → confidence → AST' },
              { icon: Database,    label: '574-vector index',       sub: 'FAISS · text-emb-3-small' },
              { icon: Cpu,         label: 'GPT-4o-mini routing',    sub: 'Conversation vs. code' },
              { icon: Sparkles,    label: 'Personal knowledge base', sub: 'Upload PDFs · cited at runtime' },
            ].map(({ icon: Icon, label, sub }) => (
              <div
                key={label}
                className="
                  group relative rounded-xl border border-white/8 bg-white/[0.03]
                  px-3.5 py-3 hover:bg-white/[0.06] hover:border-white/15
                  transition-colors
                "
              >
                <Icon size={14} className="text-primary mb-2" />
                <p className="text-[12px] font-medium text-white/85 leading-tight">{label}</p>
                <p className="text-[10.5px] text-white/40 mt-0.5">{sub}</p>
              </div>
            ))}
          </motion.div>

          {/* Cold-start warning */}
          <motion.div
            variants={item}
            className="
              mt-6 max-w-md flex items-start gap-2.5
              rounded-xl border border-amber-400/25 bg-amber-400/[0.06]
              px-3.5 py-3
            "
          >
            <Clock size={14} className="text-amber-300 mt-0.5 flex-shrink-0" />
            <div className="text-[11.5px] leading-relaxed">
              <p className="font-medium text-amber-100/95">Heads up — first request may be slow</p>
              <p className="text-amber-100/55 mt-0.5">
                Hosted on free-tier infrastructure. Cold starts can take{' '}
                <span className="text-amber-100/80 font-medium">30-60 seconds</span> after idle periods.
                Subsequent requests are fast.
              </p>
            </div>
          </motion.div>
        </div>

        {/* ── Bottom: author ─────────────────────────────────── */}
        <motion.div
          variants={item}
          className="
            relative max-w-md rounded-2xl border border-white/10
            bg-white/[0.04] backdrop-blur-sm
            px-5 py-4
          "
        >
          <p className="text-[10px] uppercase tracking-[0.14em] text-white/35 mb-2.5">
            Built by
          </p>
          <div className="flex items-start gap-4">
            <div
              className="
                w-11 h-11 rounded-full flex-shrink-0
                bg-gradient-to-br from-primary to-violet-500
                flex items-center justify-center
                font-semibold text-white text-sm shadow-md shadow-primary/30
              "
            >
              IS
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-[14px] leading-tight">Ishan Srivastava</p>
              <p className="flex items-center gap-1.5 text-[11.5px] text-white/55 mt-0.5">
                <GraduationCap size={11} className="text-white/45" />
                M.S. Applied AI · Northeastern University
              </p>

              <div className="flex items-center gap-2 mt-3">
                <a
                  href="https://www.linkedin.com/in/ishan-srivastava-7742b121a/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="
                    group inline-flex items-center gap-1.5
                    rounded-lg border border-white/10 bg-white/[0.03]
                    px-2.5 py-1.5 text-[11px] text-white/75
                    hover:bg-white/[0.08] hover:border-white/20 hover:text-white
                    transition-colors
                  "
                >
                  <Linkedin size={12} className="text-[#7aa6ff]" />
                  LinkedIn
                  <ArrowUpRight size={11} className="text-white/35 group-hover:text-white/70 transition-colors" />
                </a>
                <a
                  href="mailto:srivastava.ish@northeastern.edu"
                  className="
                    group inline-flex items-center gap-1.5
                    rounded-lg border border-white/10 bg-white/[0.03]
                    px-2.5 py-1.5 text-[11px] text-white/75
                    hover:bg-white/[0.08] hover:border-white/20 hover:text-white
                    transition-colors
                  "
                >
                  <Mail size={12} className="text-primary" />
                  srivastava.ish@northeastern.edu
                </a>
              </div>
            </div>
          </div>
        </motion.div>
      </motion.aside>

      {/* ──────────────── RIGHT PANE — auth form ──────────────── */}
      <main className="flex-1 flex items-center justify-center px-5 sm:px-10 py-10 relative">
        {/* subtle radial glow on small screens */}
        <div
          aria-hidden
          className="lg:hidden absolute inset-0 -z-10 bg-gradient-to-b from-sidebar via-sidebar-2 to-sidebar"
        />

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1], delay: 0.15 }}
          className="w-full max-w-sm"
        >
          {/* Mobile-only logo */}
          <div className="lg:hidden flex flex-col items-center mb-8">
            <div className="w-12 h-12 rounded-xl bg-primary flex items-center justify-center mb-3 shadow-lg">
              <Zap size={22} className="text-white" />
            </div>
            <h1 className="text-white font-bold text-xl tracking-tight">Omega TK</h1>
            <p className="text-white/40 text-xs mt-0.5">Code Assistant</p>
          </div>

          {/* Card */}
          <div
            className="
              relative bg-white/[0.04] border border-white/10 rounded-2xl
              p-7 shadow-2xl backdrop-blur-sm
            "
          >
            {/* Mode header */}
            <AnimatePresence mode="wait">
              <motion.div
                key={mode}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.25 }}
              >
                <h2 className="text-white font-semibold text-[17px] mb-1 tracking-tight">
                  {isLogin ? 'Welcome back' : 'Create your account'}
                </h2>
                <p className="text-white/45 text-[11.5px] mb-6 leading-relaxed">
                  {isLogin
                    ? 'Sign in to access your sessions and uploaded knowledge sources.'
                    : 'Sign up to keep your chat sessions and knowledge base across devices.'}
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
                  <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/30 rounded-xl px-3 py-2.5 text-xs text-red-300">
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
                  <div className="flex items-start gap-2 bg-emerald-500/10 border border-emerald-500/30 rounded-xl px-3 py-2.5 text-xs text-emerald-300">
                    <span>{info}</span>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Email */}
              <div className="relative">
                <Mail size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30 pointer-events-none" />
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  autoComplete="email"
                  required
                  className="
                    w-full bg-white/5 border border-white/10 rounded-xl pl-9 pr-3 py-2.5
                    text-xs text-white placeholder-white/25
                    outline-none focus:border-primary focus:ring-1 focus:ring-primary/30
                    transition-all
                  "
                />
              </div>

              {/* Password */}
              <div className="relative">
                <Lock size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30 pointer-events-none" />
                <input
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder={isLogin ? 'Password' : 'Password (min 6 chars)'}
                  autoComplete={isLogin ? 'current-password' : 'new-password'}
                  required
                  className="
                    w-full bg-white/5 border border-white/10 rounded-xl pl-9 pr-3 py-2.5
                    text-xs text-white placeholder-white/25
                    outline-none focus:border-primary focus:ring-1 focus:ring-primary/30
                    transition-all
                  "
                />
              </div>

              {/* Submit */}
              <motion.button
                type="submit"
                disabled={loading}
                whileHover={{ scale: loading ? 1 : 1.01 }}
                whileTap={{ scale: loading ? 1 : 0.99 }}
                className="
                  w-full flex items-center justify-center gap-2
                  py-2.5 rounded-xl bg-primary hover:bg-primary-dark
                  text-white text-xs font-semibold
                  transition-colors disabled:opacity-50 disabled:cursor-not-allowed
                  shadow-lg shadow-primary/20
                  mt-1
                "
              >
                {loading
                  ? <><Loader2 size={13} className="animate-spin" /> {isLogin ? 'Signing in…' : 'Creating account…'}</>
                  : btnLabel}
              </motion.button>
            </form>

            {/* Toggle */}
            <p className="text-center text-white/35 text-[11px] mt-5">
              {isLogin ? "Don't have an account?" : 'Already have an account?'}
              {' '}
              <button
                onClick={() => { setMode(isLogin ? 'signup' : 'login'); setError(null); setInfo(null) }}
                className="text-primary hover:text-primary-dark font-medium transition-colors"
              >
                {isLogin ? 'Sign up' : 'Sign in'}
              </button>
            </p>
          </div>

          {/* Mobile-only condensed cold-start notice */}
          <div className="lg:hidden mt-5 flex items-start gap-2 text-[10.5px] text-white/45 leading-relaxed px-1">
            <Clock size={11} className="text-amber-300/80 mt-0.5 flex-shrink-0" />
            <span>
              First request may take 30-60s — hosted on free-tier infrastructure that cold-starts after idle periods.
            </span>
          </div>

          {/* Footer */}
          <p className="text-center text-white/25 text-[10px] mt-6 tracking-wide">
            © {new Date().getFullYear()} Omega TK Code Assistant · Built by Ishan Srivastava
          </p>
        </motion.div>
      </main>
    </div>
  )
}
