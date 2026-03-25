/**
 * Conciliação Bancária — split-panel: transações importadas × contas P/R.
 *
 * Fluxo:
 *  1. Clique em uma transação (esquerda) → sugestões de match aparecem (direita)
 *  2. Clique em "Confirmar" numa sugestão → par conciliado
 *  3. "Auto-conciliar" → confirma todos os pares com score >= 80%
 */

import { useState, useEffect } from 'preact/hooks';
import { html } from 'htm/preact';
import {
  getConciliacaoStats,
  getConciliacaoPendentes,
  getConciliacaoSugestoes,
  confirmarConciliacao,
  autoConciliar,
  desfazerConciliacao,
} from '../../lib/api.js';

function formatBRL(val) {
  return Number(val).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}
function formatData(iso) {
  return new Date(iso + 'T00:00:00').toLocaleDateString('pt-BR');
}

function ScoreBadge({ score }) {
  const pct = Math.round(score * 100);
  const cls = pct >= 80 ? 'bg-green-100 text-green-700'
            : pct >= 60 ? 'bg-yellow-100 text-yellow-700'
                        : 'bg-gray-100 text-gray-600';
  return html`<span class=${'text-xs px-2 py-0.5 rounded-full font-semibold ' + cls}>${pct}%</span>`;
}

// ─── Cards de stats no topo ────────────────────────────────────────────────

function StatsBar({ stats, onAuto, autoLoading }) {
  if (!stats) return null;
  const pct = stats.pct_conciliado;
  const corBarra = pct >= 90 ? 'bg-green-500' : pct >= 60 ? 'bg-yellow-500' : 'bg-red-500';

  return html`
    <div class="bg-white rounded-xl border border-gray-200 p-4 mb-5">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-6">
          <div>
            <p class="text-xs text-gray-500">Total de transações</p>
            <p class="text-lg font-bold text-gray-900">${stats.total_transacoes}</p>
          </div>
          <div>
            <p class="text-xs text-gray-500">Conciliadas</p>
            <p class="text-lg font-bold text-green-700">${stats.conciliadas}</p>
          </div>
          <div>
            <p class="text-xs text-gray-500">Pendentes</p>
            <p class=${'text-lg font-bold ' + (stats.nao_conciliadas > 0 ? 'text-red-600' : 'text-gray-400')}>${stats.nao_conciliadas}</p>
          </div>
        </div>
        <button
          onClick=${onAuto}
          disabled=${autoLoading || stats.nao_conciliadas === 0}
          class="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
        >
          ${autoLoading ? html`
            <div class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            Conciliando...
          ` : html`
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            Auto-conciliar (≥ 80%)
          `}
        </button>
      </div>
      <div class="flex items-center gap-2">
        <div class="flex-1 bg-gray-100 rounded-full h-2">
          <div class=${'h-2 rounded-full transition-all ' + corBarra} style=${'width:' + Math.min(pct, 100) + '%'}></div>
        </div>
        <span class="text-xs font-semibold text-gray-600 w-10 text-right">${pct}%</span>
      </div>
    </div>
  `;
}

// ─── Painel esquerdo: transações não conciliadas ───────────────────────────

function PainelTransacoes({ transacoes, selecionada, onSelecionar, carregando }) {
  return html`
    <div class="flex flex-col h-full">
      <div class="px-4 py-3 border-b border-gray-100">
        <h2 class="text-sm font-semibold text-gray-900">Transações importadas</h2>
        <p class="text-xs text-gray-400 mt-0.5">${transacoes.length} sem conciliação</p>
      </div>
      <div class="flex-1 overflow-y-auto">
        ${carregando ? html`
          <div class="flex items-center justify-center py-12">
            <div class="w-7 h-7 border-4 border-brand-400 border-t-transparent rounded-full animate-spin"></div>
          </div>
        ` : transacoes.length === 0 ? html`
          <div class="text-center py-12">
            <svg class="w-10 h-10 text-green-300 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p class="text-sm text-gray-400">Tudo conciliado!</p>
          </div>
        ` : transacoes.map(tx => html`
          <button
            key=${tx.id}
            onClick=${() => onSelecionar(tx)}
            class=${'w-full text-left px-4 py-3 border-b border-gray-50 hover:bg-gray-50 transition-colors ' + (selecionada?.id === tx.id ? 'bg-brand-50 border-l-2 border-l-brand-500' : '')}
          >
            <div class="flex items-start justify-between gap-2">
              <div class="flex-1 min-w-0">
                <p class="text-xs font-medium text-gray-900 truncate">${tx.description}</p>
                <p class="text-xs text-gray-400 mt-0.5">${formatData(tx.date)} · ${tx.source || 'manual'}</p>
              </div>
              <p class=${'text-xs font-bold whitespace-nowrap ' + (parseFloat(tx.amount) >= 0 ? 'text-green-700' : 'text-red-700')}>
                ${parseFloat(tx.amount) >= 0 ? '+' : ''}${formatBRL(tx.amount)}
              </p>
            </div>
          </button>
        `)}
      </div>
    </div>
  `;
}

// ─── Painel direito: sugestões de match ───────────────────────────────────

function PainelSugestoes({ sugestoes, selecionada, onConfirmar, carregando }) {
  return html`
    <div class="flex flex-col h-full">
      <div class="px-4 py-3 border-b border-gray-100">
        <h2 class="text-sm font-semibold text-gray-900">
          ${selecionada ? 'Sugestões de match' : 'Todas as sugestões'}
        </h2>
        <p class="text-xs text-gray-400 mt-0.5">
          ${selecionada
            ? html`Para: <span class="font-medium">${selecionada.description}</span>`
            : `${sugestoes.length} par(es) encontrado(s)`
          }
        </p>
      </div>
      <div class="flex-1 overflow-y-auto">
        ${carregando ? html`
          <div class="flex items-center justify-center py-12">
            <div class="w-7 h-7 border-4 border-brand-400 border-t-transparent rounded-full animate-spin"></div>
          </div>
        ` : sugestoes.length === 0 ? html`
          <div class="text-center py-12 px-4">
            <svg class="w-10 h-10 text-gray-200 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            <p class="text-sm text-gray-400">
              ${selecionada ? 'Nenhuma conta P/R compatível encontrada' : 'Selecione uma transação para ver sugestões'}
            </p>
          </div>
        ` : sugestoes.map(s => html`
          <div key=${s.conta.id} class="px-4 py-3 border-b border-gray-50 hover:bg-gray-50">
            <!-- Header da sugestão -->
            <div class="flex items-start justify-between gap-2 mb-2">
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-0.5">
                  <span class=${'text-xs px-2 py-0.5 rounded-full font-medium ' + (s.conta.type === 'receivable' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700')}>
                    ${s.conta.type === 'receivable' ? 'A Receber' : 'A Pagar'}
                  </span>
                  <${ScoreBadge} score=${s.score} />
                </div>
                <p class="text-xs font-medium text-gray-900 truncate">${s.conta.description}</p>
                <p class="text-xs text-gray-400">
                  Venc. ${formatData(s.conta.due_date)}
                  ${s.conta.contact_name ? html` · ${s.conta.contact_name}` : ''}
                </p>
              </div>
              <p class="text-xs font-bold text-gray-900 whitespace-nowrap">${formatBRL(s.conta.amount)}</p>
            </div>

            <!-- Comparação de campos -->
            ${selecionada && html`
              <div class="bg-gray-50 rounded-lg p-2 mb-2 text-xs grid grid-cols-2 gap-x-3 gap-y-1">
                <div class="text-gray-400">Valor tx</div>
                <div class="font-medium">${formatBRL(selecionada.amount)}</div>
                <div class="text-gray-400">Valor conta</div>
                <div class="font-medium">${formatBRL(s.conta.amount)}</div>
                <div class="text-gray-400">Data tx</div>
                <div class="font-medium">${formatData(selecionada.date)}</div>
                <div class="text-gray-400">Vencimento</div>
                <div class="font-medium">${formatData(s.conta.due_date)}</div>
              </div>
            `}

            <button
              onClick=${() => onConfirmar(s.transacao || selecionada, s.conta)}
              class="w-full py-1.5 rounded-lg bg-brand-600 text-white text-xs font-medium hover:bg-brand-700"
            >
              Confirmar match
            </button>
          </div>
        `)}
      </div>
    </div>
  `;
}

// ─── Página principal ──────────────────────────────────────────────────────

export default function ConciliacaoPage() {
  const [stats, setStats]               = useState(null);
  const [transacoes, setTransacoes]     = useState([]);
  const [sugestoes, setSugestoes]       = useState([]);
  const [selecionada, setSelecionada]   = useState(null);
  const [loadingTx, setLoadingTx]       = useState(true);
  const [loadingSug, setLoadingSug]     = useState(false);
  const [autoLoading, setAutoLoading]   = useState(false);
  const [toast, setToast]               = useState('');

  function showToast(msg) {
    setToast(msg);
    setTimeout(() => setToast(''), 3000);
  }

  async function carregarStats() {
    try {
      const s = await getConciliacaoStats();
      setStats(s);
    } catch {}
  }

  async function carregarTransacoes() {
    setLoadingTx(true);
    try {
      const res = await getConciliacaoPendentes();
      setTransacoes(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingTx(false);
    }
  }

  async function carregarSugestoes(tx = null) {
    setLoadingSug(true);
    setSugestoes([]);
    try {
      const params = tx ? { transaction_id: tx.id } : {};
      const res = await getConciliacaoSugestoes(params);
      setSugestoes(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingSug(false);
    }
  }

  useEffect(() => {
    carregarStats();
    carregarTransacoes();
    carregarSugestoes();
  }, []);

  async function selecionar(tx) {
    if (selecionada?.id === tx.id) {
      setSelecionada(null);
      await carregarSugestoes(null);
    } else {
      setSelecionada(tx);
      await carregarSugestoes(tx);
    }
  }

  async function confirmar(tx, conta) {
    try {
      await confirmarConciliacao(tx.id, conta.id);
      showToast(`Conciliado: ${tx.description} ↔ ${conta.description}`);
      setSelecionada(null);
      await Promise.all([carregarStats(), carregarTransacoes(), carregarSugestoes()]);
    } catch (err) {
      alert(err.message);
    }
  }

  async function auto() {
    setAutoLoading(true);
    try {
      const res = await autoConciliar();
      showToast(`${res.confirmados} par(es) conciliado(s) automaticamente`);
      setSelecionada(null);
      await Promise.all([carregarStats(), carregarTransacoes(), carregarSugestoes()]);
    } catch (err) {
      alert(err.message);
    } finally {
      setAutoLoading(false);
    }
  }

  // Sugestões a exibir no painel direito
  const sugestoesFiltradas = selecionada
    ? sugestoes
    : sugestoes;

  return html`
    <div class="p-6 h-full flex flex-col max-w-7xl mx-auto">
      <!-- Header -->
      <div class="mb-5">
        <h1 class="text-xl font-bold text-gray-900">Conciliação Bancária</h1>
        <p class="text-sm text-gray-500 mt-0.5">Relacione transações importadas com contas a pagar e receber</p>
      </div>

      <!-- Stats bar -->
      <${StatsBar} stats=${stats} onAuto=${auto} autoLoading=${autoLoading} />

      <!-- Split panel -->
      <div class="flex-1 grid grid-cols-2 gap-4 min-h-0">
        <!-- Esquerda: transações -->
        <div class="bg-white rounded-xl border border-gray-200 overflow-hidden flex flex-col">
          <${PainelTransacoes}
            transacoes=${transacoes}
            selecionada=${selecionada}
            onSelecionar=${selecionar}
            carregando=${loadingTx}
          />
        </div>

        <!-- Direita: sugestões -->
        <div class="bg-white rounded-xl border border-gray-200 overflow-hidden flex flex-col">
          <${PainelSugestoes}
            sugestoes=${sugestoesFiltradas}
            selecionada=${selecionada}
            onConfirmar=${confirmar}
            carregando=${loadingSug}
          />
        </div>
      </div>

      <!-- Toast -->
      ${toast && html`
        <div class="fixed bottom-6 left-1/2 -translate-x-1/2 bg-gray-900 text-white text-sm px-5 py-3 rounded-xl shadow-lg z-50 transition-all">
          ${toast}
        </div>
      `}
    </div>
  `;
}
