/**
 * Centros de Custo — CRUD + relatório de gastos vs. orçamento.
 */

import { useState, useEffect } from 'preact/hooks';
import { html } from 'htm/preact';
import {
  getCentrosCusto,
  createCentroCusto,
  updateCentroCusto,
  deleteCentroCusto,
  getRelatorioCentroCusto,
} from '../../lib/api.js';

const TIPOS = [
  { value: 'department', label: 'Departamento' },
  { value: 'project',    label: 'Projeto' },
  { value: 'product',    label: 'Produto' },
];

const hoje = new Date();
const inicioMes = `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, '0')}-01`;
const fimMes = hoje.toISOString().slice(0, 10);

function formatBRL(val) {
  return Number(val).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

function BarraProgresso({ pct }) {
  const cor = pct >= 100 ? 'bg-red-500' : pct >= 80 ? 'bg-yellow-500' : 'bg-green-500';
  const largura = Math.min(pct, 100);
  return html`
    <div class="w-full bg-gray-100 rounded-full h-2">
      <div class=${'h-2 rounded-full transition-all ' + cor} style=${'width:' + largura + '%'}></div>
    </div>
  `;
}

function ModalCentro({ centro, onSalvar, onFechar }) {
  const [form, setForm] = useState({
    name:   centro?.name   || '',
    code:   centro?.code   || '',
    type:   centro?.type   || 'department',
    budget: centro?.budget != null ? String(centro.budget) : '',
  });
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState('');

  async function salvar(e) {
    e.preventDefault();
    if (!form.name.trim() || !form.code.trim()) {
      setErro('Nome e código são obrigatórios.');
      return;
    }
    setSalvando(true);
    setErro('');
    try {
      const payload = {
        name:   form.name.trim(),
        code:   form.code.trim().toUpperCase(),
        type:   form.type,
        budget: form.budget ? parseFloat(form.budget) : null,
      };
      await onSalvar(payload);
      onFechar();
    } catch (err) {
      setErro(err.message || 'Erro ao salvar');
    } finally {
      setSalvando(false);
    }
  }

  return html`
    <div class="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50 p-4">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-md">
        <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 class="text-base font-semibold text-gray-900">
            ${centro ? 'Editar Centro de Custo' : 'Novo Centro de Custo'}
          </h2>
          <button onClick=${onFechar} class="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
        </div>
        <form onSubmit=${salvar} class="px-6 py-4 space-y-4">
          ${erro && html`<p class="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">${erro}</p>`}
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">Nome</label>
            <input
              type="text"
              value=${form.name}
              onInput=${e => setForm(f => ({ ...f, name: e.target.value }))}
              placeholder="Ex: Marketing"
              class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              required
            />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium text-gray-700 mb-1">Código</label>
              <input
                type="text"
                value=${form.code}
                onInput=${e => setForm(f => ({ ...f, code: e.target.value }))}
                placeholder="MKT"
                maxlength="10"
                class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 uppercase"
                required
              />
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-700 mb-1">Tipo</label>
              <select
                value=${form.type}
                onChange=${e => setForm(f => ({ ...f, type: e.target.value }))}
                class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                ${TIPOS.map(t => html`<option value=${t.value}>${t.label}</option>`)}
              </select>
            </div>
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">
              Orçamento mensal (opcional)
            </label>
            <div class="relative">
              <span class="absolute left-3 top-2 text-sm text-gray-400">R$</span>
              <input
                type="number"
                value=${form.budget}
                onInput=${e => setForm(f => ({ ...f, budget: e.target.value }))}
                placeholder="0,00"
                min="0"
                step="0.01"
                class="w-full border border-gray-300 rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
          </div>
          <div class="flex gap-3 pt-2">
            <button
              type="button"
              onClick=${onFechar}
              class="flex-1 px-4 py-2 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled=${salvando}
              class="flex-1 px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-60"
            >
              ${salvando ? 'Salvando...' : 'Salvar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  `;
}

function RelatorioSlideOver({ centro, onFechar }) {
  const [dados, setDados] = useState(null);
  const [carregando, setCarregando] = useState(true);
  const [inicio, setInicio] = useState(inicioMes);
  const [fim, setFim] = useState(fimMes);

  async function carregar() {
    setCarregando(true);
    try {
      const res = await getRelatorioCentroCusto(centro.id, inicio, fim);
      setDados(res);
    } catch (err) {
      console.error(err);
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => { carregar(); }, [centro.id, inicio, fim]);

  return html`
    <div class="fixed inset-0 bg-black bg-opacity-30 flex justify-end z-50">
      <div class="w-full max-w-lg bg-white h-full flex flex-col shadow-xl">
        <!-- Header -->
        <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            <p class="text-xs text-gray-500 font-mono">${centro.code}</p>
            <h2 class="text-base font-semibold text-gray-900">${centro.name}</h2>
          </div>
          <button onClick=${onFechar} class="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
        </div>

        <!-- Filtro de período -->
        <div class="px-6 py-3 border-b border-gray-100 flex items-center gap-2">
          <input
            type="date"
            value=${inicio}
            onChange=${e => setInicio(e.target.value)}
            class="border border-gray-300 rounded-lg px-2 py-1.5 text-sm"
          />
          <span class="text-gray-400 text-sm">até</span>
          <input
            type="date"
            value=${fim}
            onChange=${e => setFim(e.target.value)}
            class="border border-gray-300 rounded-lg px-2 py-1.5 text-sm"
          />
        </div>

        <!-- Conteúdo -->
        <div class="flex-1 overflow-auto px-6 py-4">
          ${carregando ? html`
            <div class="flex items-center justify-center py-16">
              <div class="w-8 h-8 border-4 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
            </div>
          ` : dados ? html`
            <!-- Cards de resumo -->
            <div class="grid grid-cols-2 gap-3 mb-6">
              <div class="bg-gray-50 rounded-xl p-4">
                <p class="text-xs text-gray-500 mb-1">Realizado</p>
                <p class="text-lg font-bold text-gray-900">${formatBRL(dados.total_gasto)}</p>
              </div>
              <div class="bg-gray-50 rounded-xl p-4">
                <p class="text-xs text-gray-500 mb-1">Orçamento</p>
                <p class="text-lg font-bold text-gray-900">
                  ${dados.orcamento > 0 ? formatBRL(dados.orcamento) : html`<span class="text-gray-400 text-sm">Não definido</span>`}
                </p>
              </div>
            </div>

            ${dados.orcamento > 0 && html`
              <div class="mb-6">
                <div class="flex items-center justify-between mb-2">
                  <p class="text-xs text-gray-600">Utilização do orçamento</p>
                  <p class="text-xs font-semibold ${dados.utilizacao_pct >= 100 ? 'text-red-600' : dados.utilizacao_pct >= 80 ? 'text-yellow-600' : 'text-green-600'}">
                    ${dados.utilizacao_pct}%
                  </p>
                </div>
                <${BarraProgresso} pct=${dados.utilizacao_pct} />
              </div>
            `}

            <!-- Lançamentos -->
            <div>
              <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
                Lançamentos (${dados.lancamentos.length})
              </h3>
              ${dados.lancamentos.length === 0 ? html`
                <p class="text-sm text-gray-400 text-center py-8">Nenhum lançamento no período</p>
              ` : html`
                <div class="space-y-2">
                  ${dados.lancamentos.map(l => html`
                    <div class="flex items-start justify-between py-2 border-b border-gray-50 last:border-0">
                      <div class="flex-1 min-w-0 pr-3">
                        <p class="text-sm text-gray-900 truncate">${l.descricao}</p>
                        <p class="text-xs text-gray-400">
                          ${new Date(l.data + 'T00:00:00').toLocaleDateString('pt-BR')}
                          ${l.categoria ? html` · ${l.categoria}` : ''}
                        </p>
                      </div>
                      <p class="text-sm font-semibold text-red-600 whitespace-nowrap">
                        −${formatBRL(l.valor)}
                      </p>
                    </div>
                  `)}
                </div>
              `}
            </div>
          ` : html`<p class="text-sm text-gray-400 text-center py-8">Erro ao carregar relatório</p>`}
        </div>
      </div>
    </div>
  `;
}

function CardCC({ cc, onEditar, onDeletar, onVerRelatorio }) {
  const tipoBadge = {
    department: { label: 'Depto', cls: 'bg-blue-50 text-blue-700' },
    project:    { label: 'Projeto', cls: 'bg-purple-50 text-purple-700' },
    product:    { label: 'Produto', cls: 'bg-green-50 text-green-700' },
  }[cc.type] || { label: cc.type, cls: 'bg-gray-100 text-gray-600' };

  return html`
    <div class="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-sm transition-shadow">
      <div class="flex items-start justify-between mb-3">
        <div>
          <div class="flex items-center gap-2 mb-1">
            <span class="text-xs font-mono text-gray-400">${cc.code}</span>
            <span class=${'text-xs px-2 py-0.5 rounded-full font-medium ' + tipoBadge.cls}>
              ${tipoBadge.label}
            </span>
          </div>
          <h3 class="text-sm font-semibold text-gray-900">${cc.name}</h3>
        </div>
        <div class="flex items-center gap-1">
          <button
            onClick=${() => onEditar(cc)}
            class="p-1.5 text-gray-400 hover:text-brand-600 hover:bg-brand-50 rounded-lg"
            title="Editar"
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </button>
          <button
            onClick=${() => onDeletar(cc)}
            class="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg"
            title="Excluir"
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>

      ${cc.budget != null && html`
        <div class="mb-3">
          <div class="flex items-center justify-between mb-1">
            <p class="text-xs text-gray-500">Orçamento mensal</p>
            <p class="text-xs font-medium text-gray-700">${formatBRL(cc.budget)}</p>
          </div>
        </div>
      `}

      <button
        onClick=${() => onVerRelatorio(cc)}
        class="w-full text-xs text-brand-600 font-medium hover:underline text-left mt-1"
      >
        Ver relatório de gastos →
      </button>
    </div>
  `;
}

export default function CentrosCustoPage() {
  const [centros, setCentros] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState('');
  const [modalAberto, setModalAberto] = useState(false);
  const [editando, setEditando] = useState(null);
  const [relatorioCC, setRelatorioCC] = useState(null);

  async function carregar() {
    try {
      const res = await getCentrosCusto();
      setCentros(res);
    } catch (err) {
      setErro(err.message);
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => { carregar(); }, []);

  async function salvar(payload) {
    if (editando) {
      await updateCentroCusto(editando.id, payload);
    } else {
      await createCentroCusto(payload);
    }
    await carregar();
  }

  async function deletar(cc) {
    if (!confirm(`Excluir "${cc.name}"?`)) return;
    try {
      await deleteCentroCusto(cc.id);
      await carregar();
    } catch (err) {
      alert(err.message);
    }
  }

  function abrirNovo() {
    setEditando(null);
    setModalAberto(true);
  }

  function abrirEditar(cc) {
    setEditando(cc);
    setModalAberto(true);
  }

  return html`
    <div class="p-6 max-w-5xl mx-auto">
      <!-- Header -->
      <div class="flex items-center justify-between mb-6">
        <div>
          <h1 class="text-xl font-bold text-gray-900">Centros de Custo</h1>
          <p class="text-sm text-gray-500 mt-0.5">Segmente gastos por departamento, projeto ou produto</p>
        </div>
        <button
          onClick=${abrirNovo}
          class="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          Novo Centro
        </button>
      </div>

      <!-- Conteúdo -->
      ${carregando ? html`
        <div class="flex items-center justify-center py-24">
          <div class="w-10 h-10 border-4 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
        </div>
      ` : erro ? html`
        <div class="bg-red-50 text-red-700 px-4 py-3 rounded-xl text-sm">${erro}</div>
      ` : centros.length === 0 ? html`
        <div class="bg-white rounded-xl border border-dashed border-gray-300 py-16 text-center">
          <svg class="w-12 h-12 text-gray-300 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
              d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
          </svg>
          <p class="text-gray-500 text-sm mb-1">Nenhum centro de custo criado</p>
          <p class="text-gray-400 text-xs">Crie centros para segmentar seus gastos por área ou projeto</p>
          <button
            onClick=${abrirNovo}
            class="mt-4 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700"
          >
            Criar primeiro centro
          </button>
        </div>
      ` : html`
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          ${centros.map(cc => html`
            <${CardCC}
              key=${cc.id}
              cc=${cc}
              onEditar=${abrirEditar}
              onDeletar=${deletar}
              onVerRelatorio=${setRelatorioCC}
            />
          `)}
        </div>
      `}
    </div>

    <!-- Modal criar/editar -->
    ${modalAberto && html`
      <${ModalCentro}
        centro=${editando}
        onSalvar=${salvar}
        onFechar=${() => { setModalAberto(false); setEditando(null); }}
      />
    `}

    <!-- Slide-over relatório -->
    ${relatorioCC && html`
      <${RelatorioSlideOver}
        centro=${relatorioCC}
        onFechar=${() => setRelatorioCC(null)}
      />
    `}
  `;
}
