/**
 * Contas a Pagar e Receber — timeline de vencimentos, CRUD e parcelamento.
 */

import { useState, useEffect } from 'preact/hooks';
import { html } from 'htm/preact';
import {
  getContas,
  getResumoContas,
  createConta,
  updateConta,
  pagarConta,
  cancelarConta,
} from '../../lib/api.js';

const hoje = new Date();
const inicioMes = `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, '0')}-01`;
// 3 meses à frente
const fim3meses = (() => {
  const d = new Date(hoje);
  d.setMonth(d.getMonth() + 3);
  return d.toISOString().slice(0, 10);
})();

function formatBRL(val) {
  return Number(val).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}
function formatData(iso) {
  return new Date(iso + 'T00:00:00').toLocaleDateString('pt-BR');
}

const STATUS_CFG = {
  pending:   { label: 'Pendente',  cls: 'bg-gray-100 text-gray-700' },
  overdue:   { label: 'Vencida',   cls: 'bg-red-100 text-red-700' },
  paid:      { label: 'Paga',      cls: 'bg-green-100 text-green-700' },
  partial:   { label: 'Parcial',   cls: 'bg-yellow-100 text-yellow-700' },
  cancelled: { label: 'Cancelada', cls: 'bg-gray-100 text-gray-400' },
};

// Agrupa contas por mês de vencimento
function agruparPorMes(contas) {
  const grupos = {};
  for (const c of contas) {
    const mes = c.due_date.slice(0, 7); // YYYY-MM
    if (!grupos[mes]) grupos[mes] = [];
    grupos[mes].push(c);
  }
  return Object.entries(grupos).sort(([a], [b]) => a.localeCompare(b));
}

function labelMes(yyyymm) {
  const [ano, mes] = yyyymm.split('-');
  const nomes = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];
  const mesAtual = `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, '0')}`;
  const sufixo = yyyymm === mesAtual ? ' · Este mês' : '';
  return `${nomes[parseInt(mes) - 1]} ${ano}${sufixo}`;
}

// ─── Modal criar/editar ────────────────────────────────────────────────────

function ModalConta({ tipo, conta, onSalvar, onFechar }) {
  const [form, setForm] = useState({
    type:               conta?.type        || tipo || 'payable',
    description:        conta?.description || '',
    amount:             conta?.amount      != null ? String(conta.amount) : '',
    due_date:           conta?.due_date    || hoje.toISOString().slice(0, 10),
    contact_name:       conta?.contact_name || '',
    installments_total: conta?.installments_total || 1,
    recurrence:         conta?.recurrence  || '',
    notes:              conta?.notes       || '',
  });
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState('');

  async function salvar(e) {
    e.preventDefault();
    if (!form.description.trim() || !form.amount || !form.due_date) {
      setErro('Descrição, valor e vencimento são obrigatórios.');
      return;
    }
    setSalvando(true);
    setErro('');
    try {
      const payload = {
        type:               form.type,
        description:        form.description.trim(),
        amount:             parseFloat(form.amount),
        due_date:           form.due_date,
        contact_name:       form.contact_name || null,
        installments_total: parseInt(form.installments_total) || 1,
        recurrence:         form.recurrence || null,
        notes:              form.notes || null,
      };
      await onSalvar(payload);
      onFechar();
    } catch (err) {
      setErro(err.message || 'Erro ao salvar');
    } finally {
      setSalvando(false);
    }
  }

  const isParcela = parseInt(form.installments_total) > 1;

  return html`
    <div class="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50 p-4">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-md max-h-screen overflow-y-auto">
        <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between sticky top-0 bg-white">
          <h2 class="text-base font-semibold text-gray-900">
            ${conta ? 'Editar Conta' : form.type === 'payable' ? 'Nova Conta a Pagar' : 'Nova Conta a Receber'}
          </h2>
          <button onClick=${onFechar} class="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
        </div>
        <form onSubmit=${salvar} class="px-6 py-4 space-y-4">
          ${erro && html`<p class="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">${erro}</p>`}

          ${!conta && html`
            <div class="flex rounded-lg border border-gray-200 overflow-hidden">
              <button
                type="button"
                class=${'flex-1 py-2 text-sm font-medium transition-colors ' + (form.type === 'payable' ? 'bg-red-50 text-red-700' : 'text-gray-500 hover:bg-gray-50')}
                onClick=${() => setForm(f => ({ ...f, type: 'payable' }))}
              >A Pagar</button>
              <button
                type="button"
                class=${'flex-1 py-2 text-sm font-medium transition-colors ' + (form.type === 'receivable' ? 'bg-green-50 text-green-700' : 'text-gray-500 hover:bg-gray-50')}
                onClick=${() => setForm(f => ({ ...f, type: 'receivable' }))}
              >A Receber</button>
            </div>
          `}

          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">Descrição</label>
            <input
              type="text"
              value=${form.description}
              onInput=${e => setForm(f => ({ ...f, description: e.target.value }))}
              placeholder="Ex: Aluguel, Nota fiscal cliente..."
              class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              required
            />
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium text-gray-700 mb-1">Valor (R$)</label>
              <input
                type="number"
                value=${form.amount}
                onInput=${e => setForm(f => ({ ...f, amount: e.target.value }))}
                placeholder="0,00"
                min="0.01"
                step="0.01"
                class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                required
              />
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-700 mb-1">Vencimento</label>
              <input
                type="date"
                value=${form.due_date}
                onChange=${e => setForm(f => ({ ...f, due_date: e.target.value }))}
                class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                required
              />
            </div>
          </div>

          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">Contato (cliente / fornecedor)</label>
            <input
              type="text"
              value=${form.contact_name}
              onInput=${e => setForm(f => ({ ...f, contact_name: e.target.value }))}
              placeholder="Nome opcional"
              class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          ${!conta && html`
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-medium text-gray-700 mb-1">Parcelas</label>
                <input
                  type="number"
                  value=${form.installments_total}
                  onInput=${e => setForm(f => ({ ...f, installments_total: e.target.value }))}
                  min="1"
                  max="360"
                  class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div>
                <label class="block text-xs font-medium text-gray-700 mb-1">Recorrência</label>
                <select
                  value=${form.recurrence}
                  onChange=${e => setForm(f => ({ ...f, recurrence: e.target.value }))}
                  class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                >
                  <option value="">Única</option>
                  <option value="monthly">Mensal</option>
                  <option value="weekly">Semanal</option>
                  <option value="yearly">Anual</option>
                </select>
              </div>
            </div>
            ${isParcela && html`
              <p class="text-xs text-brand-600 bg-brand-50 px-3 py-2 rounded-lg">
                Serão geradas ${form.installments_total} parcelas mensais de ${form.amount ? formatBRL(parseFloat(form.amount) / parseInt(form.installments_total)) : 'R$ –'} cada.
              </p>
            `}
          `}

          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">Observações</label>
            <textarea
              value=${form.notes}
              onInput=${e => setForm(f => ({ ...f, notes: e.target.value }))}
              rows="2"
              placeholder="Opcional"
              class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
            />
          </div>

          <div class="flex gap-3 pt-2">
            <button
              type="button"
              onClick=${onFechar}
              class="flex-1 px-4 py-2 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >Cancelar</button>
            <button
              type="submit"
              disabled=${salvando}
              class="flex-1 px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-60"
            >${salvando ? 'Salvando...' : 'Salvar'}</button>
          </div>
        </form>
      </div>
    </div>
  `;
}

// ─── Linha da conta ────────────────────────────────────────────────────────

function LinhaContas({ conta, onPagar, onCancelar }) {
  const [confirmando, setConfirmando] = useState(false);
  const cfg = STATUS_CFG[conta.status] || STATUS_CFG.pending;
  const podeAcionar = !['paid', 'cancelled'].includes(conta.status);
  const isVencida   = conta.status === 'overdue';

  return html`
    <div class=${'flex items-center gap-3 py-3 border-b border-gray-50 last:border-0 ' + (isVencida ? 'bg-red-50 -mx-4 px-4 rounded-lg' : '')}>
      <!-- Dot indicador -->
      <div class=${'w-2 h-2 rounded-full flex-shrink-0 ' + (conta.type === 'receivable' ? 'bg-green-500' : isVencida ? 'bg-red-500' : 'bg-gray-400')}></div>

      <!-- Dados principais -->
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2">
          <p class="text-sm font-medium text-gray-900 truncate">${conta.description}</p>
          ${conta.installments_total > 1 && html`
            <span class="text-xs text-gray-400 whitespace-nowrap">${conta.installments_num}/${conta.installments_total}</span>
          `}
        </div>
        <div class="flex items-center gap-2 mt-0.5">
          <p class="text-xs text-gray-400">${formatData(conta.due_date)}</p>
          ${conta.contact_name && html`<span class="text-xs text-gray-400">· ${conta.contact_name}</span>`}
        </div>
      </div>

      <!-- Valor + status + ações -->
      <div class="flex items-center gap-2 flex-shrink-0">
        <p class=${'text-sm font-semibold ' + (conta.type === 'receivable' ? 'text-green-700' : isVencida ? 'text-red-700' : 'text-gray-900')}>
          ${conta.type === 'receivable' ? '+' : '−'}${formatBRL(conta.amount)}
        </p>
        <span class=${'text-xs px-2 py-0.5 rounded-full font-medium ' + cfg.cls}>${cfg.label}</span>

        ${podeAcionar && html`
          <div class="flex items-center gap-1">
            <button
              onClick=${() => !confirmando && onPagar(conta)}
              class="text-xs px-2 py-1 rounded-lg bg-green-100 text-green-700 hover:bg-green-200 font-medium"
              title="Marcar como paga"
            >✓ Pagar</button>
            <button
              onClick=${() => {
                if (confirm(`Cancelar "${conta.description}"?`)) onCancelar(conta);
              }}
              class="p-1 text-gray-300 hover:text-red-500 rounded"
              title="Cancelar"
            >
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        `}
      </div>
    </div>
  `;
}

// ─── Página principal ──────────────────────────────────────────────────────

export default function ContasPage() {
  const [aba, setAba] = useState('payable');
  const [contas, setContas] = useState([]);
  const [resumo, setResumo] = useState(null);
  const [carregando, setCarregando] = useState(true);
  const [filtroStatus, setFiltroStatus] = useState('');
  const [inicio, setInicio] = useState(inicioMes);
  const [fim, setFim] = useState(fim3meses);
  const [modalAberto, setModalAberto] = useState(false);
  const [erro, setErro] = useState('');

  async function carregar() {
    setCarregando(true);
    setErro('');
    try {
      const [lista, res] = await Promise.all([
        getContas({ type: aba, status: filtroStatus || undefined, inicio, fim }),
        getResumoContas(),
      ]);
      setContas(lista);
      setResumo(res);
    } catch (err) {
      setErro(err.message);
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => { carregar(); }, [aba, filtroStatus, inicio, fim]);

  async function salvar(payload) {
    await createConta(payload);
    await carregar();
  }

  async function pagar(conta) {
    try {
      await pagarConta(conta.id);
      await carregar();
    } catch (err) {
      alert(err.message);
    }
  }

  async function cancelar(conta) {
    try {
      await cancelarConta(conta.id);
      await carregar();
    } catch (err) {
      alert(err.message);
    }
  }

  const grupos = agruparPorMes(contas);
  const totalAba = contas
    .filter(c => !['paid', 'cancelled'].includes(c.status))
    .reduce((s, c) => s + parseFloat(c.amount), 0);

  return html`
    <div class="p-6 max-w-4xl mx-auto">
      <!-- Header -->
      <div class="flex items-center justify-between mb-6">
        <div>
          <h1 class="text-xl font-bold text-gray-900">Contas a Pagar e Receber</h1>
          <p class="text-sm text-gray-500 mt-0.5">Controle de vencimentos e fluxo de pagamentos</p>
        </div>
        <button
          onClick=${() => setModalAberto(true)}
          class="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          Nova Conta
        </button>
      </div>

      <!-- Cards de resumo -->
      ${resumo && html`
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          <div class="bg-white rounded-xl border border-gray-200 p-4">
            <p class="text-xs text-gray-500 mb-1">A Pagar</p>
            <p class="text-lg font-bold text-red-700">${formatBRL(resumo.a_pagar)}</p>
          </div>
          <div class="bg-white rounded-xl border border-gray-200 p-4">
            <p class="text-xs text-gray-500 mb-1">A Receber</p>
            <p class="text-lg font-bold text-green-700">${formatBRL(resumo.a_receber)}</p>
          </div>
          <div class="bg-white rounded-xl border border-gray-200 p-4">
            <p class="text-xs text-gray-500 mb-1">Vencidas</p>
            <p class=${'text-lg font-bold ' + (resumo.vencidos > 0 ? 'text-red-600' : 'text-gray-400')}>${formatBRL(resumo.vencidos)}</p>
          </div>
          <div class="bg-white rounded-xl border border-gray-200 p-4">
            <p class="text-xs text-gray-500 mb-1">Saldo previsto</p>
            <p class=${'text-lg font-bold ' + (resumo.saldo_previsto >= 0 ? 'text-green-700' : 'text-red-700')}>${formatBRL(resumo.saldo_previsto)}</p>
          </div>
        </div>
      `}

      <!-- Abas + filtros -->
      <div class="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div class="flex items-center gap-0 border-b border-gray-100 px-4">
          ${['payable', 'receivable'].map(t => html`
            <button
              key=${t}
              onClick=${() => setAba(t)}
              class=${'px-4 py-3 text-sm font-medium border-b-2 transition-colors ' + (aba === t ? 'border-brand-500 text-brand-700' : 'border-transparent text-gray-500 hover:text-gray-900')}
            >
              ${t === 'payable' ? 'A Pagar' : 'A Receber'}
            </button>
          `)}
          <div class="flex-1"></div>
          <!-- Filtros inline -->
          <div class="flex items-center gap-2 py-2">
            <input
              type="date"
              value=${inicio}
              onChange=${e => setInicio(e.target.value)}
              class="border border-gray-200 rounded-lg px-2 py-1 text-xs"
            />
            <span class="text-gray-400 text-xs">–</span>
            <input
              type="date"
              value=${fim}
              onChange=${e => setFim(e.target.value)}
              class="border border-gray-200 rounded-lg px-2 py-1 text-xs"
            />
            <select
              value=${filtroStatus}
              onChange=${e => setFiltroStatus(e.target.value)}
              class="border border-gray-200 rounded-lg px-2 py-1 text-xs"
            >
              <option value="">Todos</option>
              <option value="pending">Pendente</option>
              <option value="overdue">Vencida</option>
              <option value="paid">Paga</option>
              <option value="partial">Parcial</option>
            </select>
          </div>
        </div>

        <!-- Conteúdo -->
        <div class="px-4 py-2">
          ${carregando ? html`
            <div class="flex items-center justify-center py-12">
              <div class="w-8 h-8 border-4 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
            </div>
          ` : erro ? html`
            <p class="text-sm text-red-600 py-6 text-center">${erro}</p>
          ` : contas.length === 0 ? html`
            <div class="text-center py-12">
              <svg class="w-10 h-10 text-gray-200 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p class="text-sm text-gray-400">Nenhuma conta encontrada</p>
            </div>
          ` : html`
            <!-- Timeline agrupada por mês -->
            ${grupos.map(([mes, lista]) => html`
              <div key=${mes} class="mb-4">
                <div class="flex items-center justify-between py-2">
                  <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">${labelMes(mes)}</p>
                  <p class="text-xs font-semibold ${aba === 'receivable' ? 'text-green-700' : 'text-gray-700'}">
                    ${formatBRL(lista.filter(c => !['paid','cancelled'].includes(c.status)).reduce((s,c) => s + parseFloat(c.amount), 0))}
                  </p>
                </div>
                ${lista.map(c => html`
                  <${LinhaContas}
                    key=${c.id}
                    conta=${c}
                    onPagar=${pagar}
                    onCancelar=${cancelar}
                  />
                `)}
              </div>
            `)}

            <!-- Total rodapé -->
            <div class="border-t border-gray-100 pt-3 pb-2 flex items-center justify-between">
              <p class="text-xs text-gray-500">${contas.filter(c => !['paid','cancelled'].includes(c.status)).length} conta(s) em aberto</p>
              <p class=${'text-sm font-bold ' + (aba === 'receivable' ? 'text-green-700' : 'text-gray-900')}>
                Total: ${formatBRL(totalAba)}
              </p>
            </div>
          `}
        </div>
      </div>
    </div>

    ${modalAberto && html`
      <${ModalConta}
        tipo=${aba}
        conta=${null}
        onSalvar=${salvar}
        onFechar=${() => setModalAberto(false)}
      />
    `}
  `;
}
