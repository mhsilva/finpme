/**
 * Wrapper do Supabase Auth.
 * Gerencia sessão, login e logout.
 */

import { createClient } from '@supabase/supabase-js';

// Configuração do cliente Supabase (chave anon — segura para frontend)
// Valores injetados via env.js (dev local) ou Cloudflare Pages (produção)
const SUPABASE_URL      = window.__ENV__?.SUPABASE_URL;
const SUPABASE_ANON_KEY = window.__ENV__?.SUPABASE_ANON_KEY;

if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
  document.getElementById('app').innerHTML =
    '<div style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;color:#dc2626">' +
    '<p>⚠ Configuração ausente: <code>env.js</code> não encontrado ou incompleto.<br>' +
    'Consulte o README para configurar o ambiente.</p></div>';
  throw new Error('SUPABASE_URL e SUPABASE_ANON_KEY são obrigatórios.');
}

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

/**
 * Retorna a sessão ativa ou null.
 */
export async function getSession() {
  const { data } = await supabase.auth.getSession();
  return data?.session ?? null;
}

/**
 * Login com email e senha.
 * Retorna { session, error }.
 */
export async function signInWithEmail(email, password) {
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  return { session: data?.session ?? null, error };
}

/**
 * Login com Google OAuth.
 * Redireciona para o provider.
 */
export async function signInWithGoogle() {
  const { error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: { redirectTo: `${window.location.origin}/dashboard` },
  });
  if (error) throw error;
}

/**
 * Cadastro com email e senha.
 * O onboarding completo (criação de tenant) ocorre via backend.
 */
export async function signUp(email, password, dadosEmpresa) {
  const API_URL = window.__ENV__?.API_URL;

  const resposta = await fetch(`${API_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email,
      password,
      company_name: dadosEmpresa.nomeEmpresa,
      cnpj: dadosEmpresa.cnpj,
      tax_regime: dadosEmpresa.regimeFiscal || 'simples',
      full_name: dadosEmpresa.nomeCompleto,
    }),
  });

  if (!resposta.ok) {
    const erro = await resposta.json();
    throw new Error(erro.detail || 'Erro ao criar conta');
  }

  // Após criar conta no backend, faz login
  return signInWithEmail(email, password);
}

/**
 * Encerra a sessão.
 */
export async function signOut() {
  await supabase.auth.signOut();
}

/**
 * Retorna o token JWT da sessão atual.
 */
export async function getToken() {
  const session = await getSession();
  return session?.access_token ?? null;
}
