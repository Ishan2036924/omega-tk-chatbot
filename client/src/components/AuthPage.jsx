import { useState } from 'react'
import { supabase } from '../lib/supabaseClient.js'
import { Zap, Mail, Lock, AlertCircle, Loader2 } from 'lucide-react'

/**
 * AuthPage — full-screen login / sign-up form.
 * Matches the existing dark purple sidebar colour palette.
 *
 * Props:
 *   onLogin(user) — called with the Supabase user object on successful auth.
 */
export default function AuthPage({ onLogin }) {
  const [mode, setMode]         = useState('login')   // 'login' | 'signup'
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)
  const [info, setInfo]         = useState(null)       // e.g. "Check your email"

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
        if (data?.user) onLogin(data.user)
      } else {
        const { data, error: sbErr } = await supabase.auth.signUp({
          email: email.trim(),
          password,
        })
        if (sbErr) throw sbErr
        // Supabase may require email confirmation
        if (data?.user?.identities?.length === 0) {
          setInfo('An account with this email already exists. Try signing in.')
        } else if (data?.session) {
          // Email confirmation disabled — user is immediately logged in
          onLogin(data.user)
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

  return (
    <div className="min-h-screen bg-sidebar flex items-center justify-center p-4">
      <div className="w-full max-w-sm">

        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-primary flex items-center justify-center mb-3 shadow-lg">
            <Zap size={22} className="text-white" />
          </div>
          <h1 className="text-white font-bold text-xl tracking-tight">Omega TK</h1>
          <p className="text-white/40 text-xs mt-0.5">Code Assistant</p>
        </div>

        {/* Card */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-7 shadow-2xl">
          <h2 className="text-white font-semibold text-base mb-1">
            {isLogin ? 'Welcome back' : 'Create an account'}
          </h2>
          <p className="text-white/40 text-xs mb-6">
            {isLogin
              ? 'Sign in to access your sessions and knowledge base.'
              : 'Sign up to save your sessions and knowledge base permanently.'}
          </p>

          {/* Error / info banners */}
          {error && (
            <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/30 rounded-xl px-3 py-2.5 mb-4 text-xs text-red-300">
              <AlertCircle size={13} className="flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}
          {info && (
            <div className="flex items-start gap-2 bg-emerald-500/10 border border-emerald-500/30 rounded-xl px-3 py-2.5 mb-4 text-xs text-emerald-300">
              <span>{info}</span>
            </div>
          )}

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
            <button
              type="submit"
              disabled={loading}
              className="
                w-full flex items-center justify-center gap-2
                py-2.5 rounded-xl bg-primary hover:bg-primary-dark
                text-white text-xs font-semibold
                transition-colors disabled:opacity-50 disabled:cursor-not-allowed
                mt-1
              "
            >
              {loading
                ? <><Loader2 size={13} className="animate-spin" /> {isLogin ? 'Signing in…' : 'Creating account…'}</>
                : btnLabel}
            </button>
          </form>

          {/* Toggle login / signup */}
          <p className="text-center text-white/30 text-[11px] mt-5">
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
      </div>
    </div>
  )
}
