/**
 * Configuração do frontend para desenvolvimento local.
 * Copie este arquivo para env.js e ajuste os valores.
 *
 *   cp frontend/env.example.js frontend/env.js
 *
 * env.js está no .gitignore — nunca commite a chave real.
 */

window.__ENV__ = {
  // Supabase local (padrão do `supabase start`)
  SUPABASE_URL: 'http://127.0.0.1:54321',

  // chave anon padrão do Supabase CLI
  SUPABASE_ANON_KEY: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRFA0NiK7kyqd6Oh7tOQgKVJWjmcAz3TY3YjM_0Vc4Q',

  // Backend FastAPI local
  API_URL: 'http://localhost:8000',
};
