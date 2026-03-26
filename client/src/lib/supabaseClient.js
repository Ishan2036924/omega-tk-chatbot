import { createClient } from '@supabase/supabase-js'

/**
 * Singleton Supabase JS client.
 * Reads VITE_SUPABASE_URL and VITE_SUPABASE_KEY from the Vite environment.
 * These must be set in client/.env (or Vercel/Render env vars in production).
 */
export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_KEY,
)
