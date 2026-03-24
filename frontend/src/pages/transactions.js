/**
 * Página de Lançamentos.
 * Tabela com filtros, inline edit de categoria e badge de confiança IA.
 */

import { useState, useEffect } from 'preact/hooks';
import { html } from 'htm/preact';
import { getTransactions, updateTransaction, deleteTransaction } from '../lib/api.js';

const CATEGORIAS_DRE = [
  'Receitas de Vendas', 'Prestação de Serviços', 'Devoluções',
  'Custo das Mercadorias Vendidas', 'Custo de Serviços',
  'Despesas com Pessoal', 'Aluguel e Condomínio', 'Energia Elétrica',
  'Telefonia e Internet', 'Marketing e Publicidade', 'Contabilidade',
  'TI e Software', 'Tarifas Bancárias', 'Juros Pagos', 'Outras Despesas',
];

function hoje() { return new Date().toISOString().slice(0, 10); }
function inicioMes() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
}

function formatarMoeda(valor) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(valor || 0);
}

function BadgeConfianca({ confianca }) {
  if (confianca == null) return null;
  const pct = Math.round(confianca * 100);
  const cor = pct >= 85 ? 'bg-emerald-100 text-emerald-700'
    : pct >= 60 ? 'bg-yellow-100 text-yellow-700'
    : 'bg-red-100 text-red-700';
  return html`<span class=${'text-xs font-medium px-1.5 py-0.5 rounded ' + cor}>${pct}%</span>`;
}

export default function TransactionsPage() {
  const [transacoes, setTransacoes] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [editandoId, setEditandoId] = useState(null);
  const [filtros, setFiltros] = useState({ inicio: inicioMes(), fim: hoje(), tipo: '' });
  const [salvando, setSalvando] = useState(null);

  useEffect(() => {
    carregarTransacoes();
  }, [filtros]);

  async function carregarTransacoes() {
    setCarregando(true);
    try {
      const lista = await getTransactions(filtros);
      setTransacoes(lista);
    } catch {
      // silencia
    } finally {
      setCarregando(false);
    }
  }

  async function salvarCategoria(id, categoria) {
    setSalvando(id);
    try {
      const atualizada = await updateTransaction(id, { category: categoria, confirmed: true });
      setTransacoes(prev => prev.map(t => t.id === id ? { ...t, ...atualizada, confirmed: true } : t));
    } catch {
      // silencia
    } finally {
      setSalvando(null);
      setEditandoId(null);
    }
  }

  async function confirmar(id) {
    setSalvando(id);
    try {
      await updateTransaction(id, { confirmed: true });
      setTransacoes(prev => prev.map(t => t.id === id ? { ...t, confirmed: true } : t));
    } catch {
      // silencia
    } finally {
      setSalvando(null);
    }
  }

  async function remover(id) {
    if (!confirm('Remover este lançamento?')) return;
    try {
      await deleteTransaction(id);
      setTransacoes(prev => prev.filter(t => t.id !== id));
    } catch {
      // silencia
    }
  }

  return html`
    <div class="p-6 max-w-6xl mx-auto space-y-5">
      <div>
        <h2 class="text-xl font-semibold text-gray-900">Lançamentos</h2>
        <p class="text-sm text-gray-500">${transacoes.length} transações encontradas</p>
      </div>

      <!-- Filtros -->
      <div class="bg-white rounded-xl border border-gray-200 p-4 flex flex-wrap gap-3 items-end">
        <div>
          <label class="block text-xs font-medium text-gray-600 mb-1">Data início</label>
          <input
            type="date"
            value=${filtros.inicio}
            onChange=${e => setFiltros(f => ({ ...f, inicio: e.target.value }))}
            class="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-600 mb-1">Data fim</label>
          <input
            type="date"
            value=${filtros.fim}
            onChange=${e => setFiltros(f => ({ ...f, fim: e.target.value }))}
            class="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-600 mb-1">Tipo</label>
          <select
            value=${filtros.tipo}
            onChange=${e => setFiltros(f => ({ ...f, tipo: e.target.value }))}
            class="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">Todos</option>
            <option value="entrada">Entradas</option>
            <option value="saida">Saídas</option>
          </select>
        </div>
      </div>

      <!-- Tabela -->
      <div class="bg-white rounded-xl border border-gray-200 overflow-hidden">
        ${carregando
          ? html`<div class="flex justify-center py-12"><div class="w-8 h-8 border-4 border-brand-500 border-t-transparent rounded-full animate-spin"></div></div>`
          : transacoes.length === 0
          ? html`<p class="text-sm text-gray-400 text-center py-12">Nenhuma transação encontrada no período.</p>`
          : html`
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="bg-gray-50 border-b border-gray-200">
                    <th class="text-left px-4 py-3 font-medium text-gray-600 text-xs">Data</th>
                    <th class="text-left px-4 py-3 font-medium text-gray-600 text-xs">Descrição</th>
                    <th class="text-left px-4 py-3 font-medium text-gray-600 text-xs">Categoria</th>
                    <th class="text-right px-4 py-3 font-medium text-gray-600 text-xs">Valor</th>
                    <th class="text-center px-4 py-3 font-medium text-gray-600 text-xs">IA</th>
                    <th class="text-center px-4 py-3 font-medium text-gray-600 text-xs">Ações</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-100">
                  ${transacoes.map(t => html`
                    <tr key=${t.id} class="hover:bg-gray-50 transition-colors">
                      <td class="px-4 py-3 text-gray-500 whitespace-nowrap">${t.date}</td>
                      <td class="px-4 py-3 text-gray-800 max-w-xs">
                        <p class="truncate">${t.description}</p>
                        ${t.confirmed && html`<span class="text-xs text-emerald-600">✓ Confirmado</span>`}
                      </td>
                      <td class="px-4 py-3">
                        ${editandoId === t.id
                          ? html`
                            <select
                              class="border border-brand-400 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-brand-500"
                              value=${t.category || ''}
                              disabled=${salvando === t.id}
                              onChange=${e => salvarCategoria(t.id, e.target.value)}
                              onBlur=${() => setEditandoId(null)}
                            >
                              <option value="">— Selecione —</option>
                              ${CATEGORIAS_DRE.map(c => html`<option key=${c} value=${c}>${c}</option>`)}
                            </select>
                          `
                          : html`
                            <span
                              class="text-xs text-gray-600 cursor-pointer hover:text-brand-600 hover:underline"
                              onClick=${() => setEditandoId(t.id)}
                              title="Clique para editar"
                            >
                              ${t.category || html`<em class="text-gray-300">Não categorizado</em>`}
                            </span>
                          `
                        }
                      </td>
                      <td class=${'px-4 py-3 text-right font-semibold whitespace-nowrap ' + (t.amount > 0 ? 'text-emerald-600' : 'text-red-600')}>
                        ${formatarMoeda(t.amount)}
                      </td>
                      <td class="px-4 py-3 text-center">
                        ${t.ai_categorized
                          ? html`<${BadgeConfianca} confianca=${t.ai_confidence} />`
                          : html`<span class="text-xs text-gray-300">—</span>`
                        }
                      </td>
                      <td class="px-4 py-3 text-center">
                        <div class="flex items-center justify-center gap-2">
                          ${!t.confirmed && html`
                            <button
                              onClick=${() => confirmar(t.id)}
                              disabled=${salvando === t.id}
                              class="text-gray-400 hover:text-emerald-500 transition-colors disabled:opacity-40"
                              title="Confirmar pagamento"
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7" />
                              </svg>
                            </button>
                          `}
                          <button
                            onClick=${() => remover(t.id)}
                            class="text-gray-400 hover:text-red-500 transition-colors"
                            title="Remover"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </div>
                      </td>
                    </tr>
                  `)}
                </tbody>
              </table>
            </div>
          `
        }
      </div>
    </div>
  `;
}
