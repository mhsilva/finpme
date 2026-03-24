/**
 * Página de Login e Cadastro.
 */

import { useState } from 'preact/hooks';
import { html } from 'htm/preact';
import { signInWithEmail, signInWithGoogle, signUp } from '../lib/auth.js';

export default function LoginPage({ onLogin, onNavegar }) {
  const [aba, setAba] = useState('login'); // 'login' | 'cadastro'
  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [nomeCompleto, setNomeCompleto] = useState('');
  const [nomeEmpresa, setNomeEmpresa] = useState('');
  const [cnpj, setCnpj] = useState('');
  const [regime, setRegime] = useState('simples');
  const [erro, setErro] = useState('');
  const [carregando, setCarregando] = useState(false);

  async function handleLogin(e) {
    e.preventDefault();
    setErro('');
    setCarregando(true);
    try {
      const { session, error } = await signInWithEmail(email, senha);
      if (error) throw error;
      onLogin(session);
    } catch (err) {
      setErro(err.message || 'Erro ao fazer login. Verifique suas credenciais.');
    } finally {
      setCarregando(false);
    }
  }

  async function handleCadastro(e) {
    e.preventDefault();
    setErro('');
    setCarregando(true);
    try {
      const { session, error } = await signUp(email, senha, {
        nomeCompleto, nomeEmpresa, cnpj, regimeFiscal: regime,
      });
      if (error) throw error;
      onLogin(session);
    } catch (err) {
      setErro(err.message || 'Erro ao criar conta.');
    } finally {
      setCarregando(false);
    }
  }

  async function handleGoogle() {
    setErro('');
    try {
      await signInWithGoogle();
    } catch (err) {
      setErro('Erro ao conectar com Google.');
    }
  }

  return html`
    <div class="min-h-screen bg-gradient-to-br from-brand-50 to-white flex items-center justify-center p-4">
      <div class="w-full max-w-md">
        <!-- Logo -->
        <div class="text-center mb-8">
          <h1 class="text-3xl font-bold text-brand-700">Fin<span class="text-gray-900">PME</span></h1>
          <p class="text-gray-500 mt-1">Inteligência financeira para o seu negócio</p>
        </div>

        <div class="bg-white rounded-2xl shadow-lg p-8">
          <!-- Abas -->
          <div class="flex border-b border-gray-200 mb-6">
            <button
              class=${'flex-1 pb-3 text-sm font-medium border-b-2 transition-colors ' + (aba === 'login' ? 'border-brand-500 text-brand-600' : 'border-transparent text-gray-500 hover:text-gray-700')}
              onClick=${() => { setAba('login'); setErro(''); }}
            >Entrar</button>
            <button
              class=${'flex-1 pb-3 text-sm font-medium border-b-2 transition-colors ' + (aba === 'cadastro' ? 'border-brand-500 text-brand-600' : 'border-transparent text-gray-500 hover:text-gray-700')}
              onClick=${() => { setAba('cadastro'); setErro(''); }}
            >Criar conta</button>
          </div>

          <!-- Mensagem de erro -->
          ${erro && html`
            <div class="bg-red-50 text-red-700 border border-red-200 rounded-lg px-4 py-3 text-sm mb-4">
              ${erro}
            </div>
          `}

          <!-- Login -->
          ${aba === 'login' && html`
            <form onSubmit=${handleLogin} class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">E-mail</label>
                <input
                  type="email"
                  required
                  value=${email}
                  onInput=${e => setEmail(e.target.value)}
                  placeholder="voce@empresa.com"
                  class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Senha</label>
                <input
                  type="password"
                  required
                  value=${senha}
                  onInput=${e => setSenha(e.target.value)}
                  placeholder="••••••••"
                  class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                />
              </div>
              <button
                type="submit"
                disabled=${carregando}
                class="w-full bg-brand-600 hover:bg-brand-700 text-white font-medium py-2.5 rounded-lg text-sm transition-colors disabled:opacity-60"
              >
                ${carregando ? 'Entrando...' : 'Entrar'}
              </button>
            </form>

            <div class="relative my-5">
              <div class="absolute inset-0 flex items-center"><div class="w-full border-t border-gray-200"></div></div>
              <div class="relative flex justify-center"><span class="bg-white px-3 text-xs text-gray-400">ou</span></div>
            </div>

            <button
              onClick=${handleGoogle}
              class="w-full border border-gray-300 hover:bg-gray-50 text-gray-700 font-medium py-2.5 rounded-lg text-sm transition-colors flex items-center justify-center gap-2"
            >
              <svg class="w-4 h-4" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
              Entrar com Google
            </button>
          `}

          <!-- Cadastro -->
          ${aba === 'cadastro' && html`
            <form onSubmit=${handleCadastro} class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Nome completo</label>
                <input
                  type="text"
                  required
                  value=${nomeCompleto}
                  onInput=${e => setNomeCompleto(e.target.value)}
                  placeholder="João Silva"
                  class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Nome da empresa</label>
                <input
                  type="text"
                  required
                  value=${nomeEmpresa}
                  onInput=${e => setNomeEmpresa(e.target.value)}
                  placeholder="Minha Empresa Ltda"
                  class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">CNPJ (opcional)</label>
                <input
                  type="text"
                  value=${cnpj}
                  onInput=${e => setCnpj(e.target.value)}
                  placeholder="00.000.000/0001-00"
                  class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Regime fiscal</label>
                <select
                  value=${regime}
                  onChange=${e => setRegime(e.target.value)}
                  class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                >
                  <option value="simples">Simples Nacional</option>
                  <option value="presumido">Lucro Presumido</option>
                  <option value="real">Lucro Real</option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">E-mail</label>
                <input
                  type="email"
                  required
                  value=${email}
                  onInput=${e => setEmail(e.target.value)}
                  placeholder="voce@empresa.com"
                  class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Senha</label>
                <input
                  type="password"
                  required
                  minLength="8"
                  value=${senha}
                  onInput=${e => setSenha(e.target.value)}
                  placeholder="Mínimo 8 caracteres"
                  class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <button
                type="submit"
                disabled=${carregando}
                class="w-full bg-brand-600 hover:bg-brand-700 text-white font-medium py-2.5 rounded-lg text-sm transition-colors disabled:opacity-60"
              >
                ${carregando ? 'Criando conta...' : 'Criar conta grátis'}
              </button>
            </form>
          `}
        </div>
      </div>
    </div>
  `;
}
