/**
 * Página de Relatórios.
 * Tabs: DRE | Fluxo de Caixa com seletor de período e exportação CSV.
 */

import { useState, useEffect } from 'preact/hooks';
import { html } from 'htm/preact';
import { getDRE, getCashFlow } from '../lib/api.js';

function hoje() { return new Date().toISOString().slice(0, 10); }
function inicioMes() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
}

function formatarMoeda(v) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v || 0);
}

function formatarPct(v) {
  return v != null ? `${v.toFixed(1)}%` : '—';
}

// ---------------------------------------------------------------------------
// Componente DRE
// ---------------------------------------------------------------------------
function TabelaDRE({ dre }) {
  if (!dre) return html`<p class="text-sm text-gray-400 text-center py-8">Sem dados no período selecionado.</p>`;

  const linhas = [
    { label: 'Receita Bruta',              valor: dre.receita_bruta,            destaque: false, negrita: false },
    { label: '(−) Deduções e Impostos',    valor: -dre.deducoes,                destaque: false, negrita: false },
    { label: 'Receita Líquida',            valor: dre.receita_liquida,           destaque: true,  negrita: true  },
    { label: '(−) Custo das Merc. Vendidas', valor: -dre.cmv,                   destaque: false, negrita: false },
    { label: 'Lucro Bruto',                valor: dre.lucro_bruto,               destaque: true,  negrita: true  },
    { label: '(−) Desp. de Vendas',        valor: -dre.despesa_vendas,           destaque: false, negrita: false },
    { label: '(−) Desp. Administrativas',  valor: -dre.despesa_admin,            destaque: false, negrita: false },
    { label: 'EBITDA',                     valor: dre.ebitda,                    destaque: true,  negrita: true  },
    { label: '(−) Desp. Financeiras',      valor: -dre.despesa_financeira,       destaque: false, negrita: false },
    { label: 'Outros',                     valor: dre.outros,                    destaque: false, negrita: false },
    { label: 'Lucro Líquido',              valor: dre.lucro_liquido,             destaque: true,  negrita: true, grande: true },
  ];

  const receitaLiquida = dre.receita_liquida || 1;

  return html`
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="bg-gray-50 border-b border-gray-200">
            <th class="text-left px-4 py-3 font-medium text-gray-600 text-xs">Descrição</th>
            <th class="text-right px-4 py-3 font-medium text-gray-600 text-xs">Valor</th>
            <th class="text-right px-4 py-3 font-medium text-gray-600 text-xs">% Rec. Líquida</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          ${linhas.map((l, i) => html`
            <tr key=${i} class=${l.destaque ? 'bg-gray-50' : ''}>
              <td class=${'px-4 py-2.5 text-gray-700 ' + (l.negrita ? 'font-semibold' : '') + (l.grande ? ' text-base' : '')}>
                ${l.label}
              </td>
              <td class=${'px-4 py-2.5 text-right ' + (l.negrita ? 'font-semibold' : '') + (l.valor >= 0 ? ' text-gray-800' : ' text-red-600') + (l.grande ? ' text-base' : '')}>
                ${formatarMoeda(l.valor)}
              </td>
              <td class="px-4 py-2.5 text-right text-gray-400 text-xs">
                ${l.destaque ? formatarPct((l.valor / receitaLiquida) * 100) : ''}
              </td>
            </tr>
          `)}
        </tbody>
      </table>

      <!-- Margens -->
      <div class="border-t border-gray-200 px-4 py-3 flex gap-6 flex-wrap">
        <div>
          <p class="text-xs text-gray-400">Margem Bruta</p>
          <p class="text-sm font-semibold text-gray-800">${formatarPct(dre.margem_bruta)}</p>
        </div>
        <div>
          <p class="text-xs text-gray-400">Margem EBITDA</p>
          <p class="text-sm font-semibold text-gray-800">${formatarPct(dre.margem_ebitda)}</p>
        </div>
        <div>
          <p class="text-xs text-gray-400">Margem Líquida</p>
          <p class=${'text-sm font-semibold ' + (dre.margem_liquida >= 0 ? 'text-emerald-600' : 'text-red-600')}>
            ${formatarPct(dre.margem_liquida)}
          </p>
        </div>
      </div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Componente Fluxo de Caixa
// ---------------------------------------------------------------------------
function TabelaCashFlow({ cashflow }) {
  if (!cashflow) return html`<p class="text-sm text-gray-400 text-center py-8">Sem dados no período selecionado.</p>`;

  return html`
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="bg-gray-50 border-b border-gray-200">
            <th class="text-left px-4 py-3 font-medium text-gray-600 text-xs">Semana</th>
            <th class="text-right px-4 py-3 font-medium text-gray-600 text-xs">Entradas</th>
            <th class="text-right px-4 py-3 font-medium text-gray-600 text-xs">Saídas</th>
            <th class="text-right px-4 py-3 font-medium text-gray-600 text-xs">Saldo Período</th>
            <th class="text-right px-4 py-3 font-medium text-gray-600 text-xs">Saldo Acumulado</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          ${cashflow.entries.map((e, i) => html`
            <tr key=${i} class="hover:bg-gray-50">
              <td class="px-4 py-2.5 text-gray-600">${e.period}</td>
              <td class="px-4 py-2.5 text-right text-emerald-600">${formatarMoeda(e.entradas)}</td>
              <td class="px-4 py-2.5 text-right text-red-600">${formatarMoeda(e.saidas)}</td>
              <td class=${'px-4 py-2.5 text-right font-medium ' + (e.saldo_periodo >= 0 ? 'text-emerald-600' : 'text-red-600')}>
                ${formatarMoeda(e.saldo_periodo)}
              </td>
              <td class=${'px-4 py-2.5 text-right font-semibold ' + (e.saldo_acumulado >= 0 ? 'text-gray-800' : 'text-red-700')}>
                ${formatarMoeda(e.saldo_acumulado)}
              </td>
            </tr>
          `)}
        </tbody>
        <tfoot class="border-t-2 border-gray-300 bg-gray-50">
          <tr>
            <td class="px-4 py-3 font-semibold text-gray-700">Total</td>
            <td class="px-4 py-3 text-right font-semibold text-emerald-600">${formatarMoeda(cashflow.total_entradas)}</td>
            <td class="px-4 py-3 text-right font-semibold text-red-600">${formatarMoeda(cashflow.total_saidas)}</td>
            <td class="px-4 py-3 text-right font-semibold"></td>
            <td class=${'px-4 py-3 text-right font-bold text-base ' + (cashflow.saldo_final >= 0 ? 'text-emerald-700' : 'text-red-700')}>
              ${formatarMoeda(cashflow.saldo_final)}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Página principal
// ---------------------------------------------------------------------------
export default function ReportsPage() {
  const [aba, setAba] = useState('dre');
  const [inicio, setInicio] = useState(inicioMes());
  const [fim, setFim] = useState(hoje());
  const [dre, setDre] = useState(null);
  const [cashflow, setCashflow] = useState(null);
  const [carregando, setCarregando] = useState(false);

  useEffect(() => {
    carregar();
  }, [inicio, fim]);

  async function carregar() {
    setCarregando(true);
    try {
      const [d, c] = await Promise.all([
        getDRE(inicio, fim).catch(() => null),
        getCashFlow(inicio, fim).catch(() => null),
      ]);
      setDre(d);
      setCashflow(c);
    } finally {
      setCarregando(false);
    }
  }

  function exportarCSV() {
    const dados = aba === 'dre' ? dre : cashflow;
    if (!dados) return;

    let csv = '';
    if (aba === 'dre') {
      csv = 'Descrição,Valor,% Receita Líquida\n';
      const linhas = [
        ['Receita Bruta', dados.receita_bruta],
        ['Deduções', -dados.deducoes],
        ['Receita Líquida', dados.receita_liquida],
        ['CMV', -dados.cmv],
        ['Lucro Bruto', dados.lucro_bruto],
        ['Desp. Vendas', -dados.despesa_vendas],
        ['Desp. Admin', -dados.despesa_admin],
        ['EBITDA', dados.ebitda],
        ['Desp. Financeiras', -dados.despesa_financeira],
        ['Lucro Líquido', dados.lucro_liquido],
      ];
      const recLiq = dados.receita_liquida || 1;
      linhas.forEach(([l, v]) => { csv += `"${l}",${v},${((v / recLiq) * 100).toFixed(2)}%\n`; });
    } else {
      csv = 'Semana,Entradas,Saídas,Saldo Período,Saldo Acumulado\n';
      dados.entries.forEach(e => {
        csv += `${e.period},${e.entradas},${e.saidas},${e.saldo_periodo},${e.saldo_acumulado}\n`;
      });
    }

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `finpme_${aba}_${inicio}_${fim}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return html`
    <div class="p-6 max-w-5xl mx-auto space-y-5">
      <!-- Cabeçalho -->
      <div class="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h2 class="text-xl font-semibold text-gray-900">Relatórios</h2>
          <p class="text-sm text-gray-500">DRE e Fluxo de Caixa</p>
        </div>

        <!-- Seletor de período + exportar -->
        <div class="flex items-end gap-3 flex-wrap">
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">Início</label>
            <input
              type="date"
              value=${inicio}
              onChange=${e => setInicio(e.target.value)}
              class="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 mb-1">Fim</label>
            <input
              type="date"
              value=${fim}
              onChange=${e => setFim(e.target.value)}
              class="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <button
            onClick=${exportarCSV}
            class="flex items-center gap-1.5 border border-gray-300 hover:bg-gray-50 text-gray-700 px-3 py-1.5 rounded-lg text-sm transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Exportar CSV
          </button>
        </div>
      </div>

      <!-- Tabs -->
      <div class="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div class="border-b border-gray-200 flex">
          <button
            class=${'flex-none px-6 py-3 text-sm font-medium border-b-2 transition-colors ' + (aba === 'dre' ? 'border-brand-500 text-brand-600' : 'border-transparent text-gray-500 hover:text-gray-700')}
            onClick=${() => setAba('dre')}
          >DRE</button>
          <button
            class=${'flex-none px-6 py-3 text-sm font-medium border-b-2 transition-colors ' + (aba === 'cashflow' ? 'border-brand-500 text-brand-600' : 'border-transparent text-gray-500 hover:text-gray-700')}
            onClick=${() => setAba('cashflow')}
          >Fluxo de Caixa</button>
        </div>

        ${carregando
          ? html`<div class="flex justify-center py-12"><div class="w-8 h-8 border-4 border-brand-500 border-t-transparent rounded-full animate-spin"></div></div>`
          : aba === 'dre'
          ? html`<${TabelaDRE} dre=${dre} />`
          : html`<${TabelaCashFlow} cashflow=${cashflow} />`
        }
      </div>
    </div>
  `;
}
