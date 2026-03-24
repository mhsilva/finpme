/**
 * FinPME – Ponto de entrada da SPA
 * Inicializa o roteador e monta o componente raiz.
 */

import { render, h } from 'preact';
import { useState, useEffect } from 'preact/hooks';
import { html } from 'htm/preact';

import { router } from './lib/router.js';
import { getSession } from './lib/auth.js';

import LoginPage from './pages/login.js';
import DashboardPage from './pages/dashboard.js';
import UploadPage from './pages/upload.js';
import TransactionsPage from './pages/transactions.js';
import ReportsPage from './pages/reports.js';

// Ícones SVG inline simples
const icons = {
  dashboard: html`<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" /></svg>`,
  upload: html`<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>`,
  transactions: html`<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>`,
  reports: html`<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>`,
  logout: html`<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>`,
};

const NAVEGACAO = [
  { rota: '/dashboard',    label: 'Dashboard',    icon: icons.dashboard },
  { rota: '/upload',       label: 'Upload',       icon: icons.upload },
  { rota: '/transactions', label: 'Lançamentos',  icon: icons.transactions },
  { rota: '/reports',      label: 'Relatórios',   icon: icons.reports },
];

function Sidebar({ rotaAtual, onNavegar, onSair }) {
  return html`
    <aside class="w-64 bg-white border-r border-gray-200 flex flex-col h-screen sticky top-0">
      <!-- Logo -->
      <div class="px-6 py-5 border-b border-gray-200">
        <h1 class="text-xl font-bold text-brand-700">
          Fin<span class="text-gray-900">PME</span>
        </h1>
        <p class="text-xs text-gray-400 mt-0.5">Inteligência Financeira</p>
      </div>

      <!-- Links de navegação -->
      <nav class="flex-1 px-3 py-4 space-y-1">
        ${NAVEGACAO.map(item => html`
          <a
            key=${item.rota}
            href="#"
            class=${'sidebar-link' + (rotaAtual === item.rota ? ' active' : '')}
            onClick=${(e) => { e.preventDefault(); onNavegar(item.rota); }}
          >
            ${item.icon}
            ${item.label}
          </a>
        `)}
      </nav>

      <!-- Rodapé -->
      <div class="px-3 py-4 border-t border-gray-200">
        <button
          onClick=${onSair}
          class="sidebar-link w-full text-red-600 hover:bg-red-50 hover:text-red-700"
        >
          ${icons.logout}
          Sair
        </button>
      </div>
    </aside>
  `;
}

function App() {
  const [rota, setRota] = useState(router.obterRota());
  const [sessao, setSessao] = useState(null);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    async function verificarSessao() {
      const s = await getSession();
      setSessao(s);
      setCarregando(false);

      if (!s && rota !== '/login' && rota !== '/register') {
        setRota('/login');
        router.navegar('/login');
      } else if (s && (rota === '/login' || rota === '/register' || rota === '/')) {
        setRota('/dashboard');
        router.navegar('/dashboard');
      }
    }
    verificarSessao();

    // Escuta mudanças de rota
    const desvincular = router.aoMudar((novaRota) => setRota(novaRota));
    return desvincular;
  }, []);

  function navegar(novaRota) {
    router.navegar(novaRota);
    setRota(novaRota);
  }

  async function sair() {
    const { signOut } = await import('./lib/auth.js');
    await signOut();
    setSessao(null);
    navegar('/login');
  }

  if (carregando) {
    return html`
      <div class="flex items-center justify-center min-h-screen">
        <div class="w-10 h-10 border-4 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    `;
  }

  // Páginas sem autenticação
  if (!sessao || rota === '/login' || rota === '/register') {
    return html`<${LoginPage} onLogin=${(s) => { setSessao(s); navegar('/dashboard'); }} onNavegar=${navegar} />`;
  }

  // Layout autenticado com sidebar
  let PaginaAtual;
  switch (rota) {
    case '/dashboard':    PaginaAtual = DashboardPage; break;
    case '/upload':       PaginaAtual = UploadPage; break;
    case '/transactions': PaginaAtual = TransactionsPage; break;
    case '/reports':      PaginaAtual = ReportsPage; break;
    default:              PaginaAtual = DashboardPage;
  }

  return html`
    <div class="flex h-screen overflow-hidden">
      <${Sidebar} rotaAtual=${rota} onNavegar=${navegar} onSair=${sair} />
      <main class="flex-1 overflow-auto bg-gray-50">
        <${PaginaAtual} sessao=${sessao} />
      </main>
    </div>
  `;
}

render(html`<${App} />`, document.getElementById('app'));
