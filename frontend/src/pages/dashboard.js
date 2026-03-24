/**
 * Página de Dashboard.
 * Exibe cards de resumo financeiro, gráfico e últimas transações.
 */

import { useState, useEffect } from 'preact/hooks';
import { html } from 'htm/preact';
import { getDRE, getCashFlow, getTransactions } from '../lib/api.js';

function hoje() {
  return new Date().toISOString().slice(0, 10);
}

function inicioMes() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
}

function formatarMoeda(valor) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(valor || 0);
}

function Card({ titulo, valor, variante = 'neutro', subtitulo }) {
  const cores = {
    positivo: 'text-emerald-600',
    negativo: 'text-red-600',
    neutro: 'text-gray-900',
  };
  return html`
    <div class="bg-white rounded-xl border border-gray-200 p-5">
      <p class="text-xs font-medium text-gray-500 uppercase tracking-wide">${titulo}</p>
      <p class=${'text-2xl font-bold mt-1 ' + cores[variante]}>${valor}</p>
      ${subtitulo && html`<p class="text-xs text-gray-400 mt-1">${subtitulo}</p>`}
    </div>
  `;
}

function GraficoBarras({ dados }) {
  if (!dados || dados.length === 0) return html`<p class="text-sm text-gray-400 text-center py-8">Sem dados no período</p>`;

  const maxValor = Math.max(...dados.map(d => Math.max(d.entradas, d.saidas)), 1);
  const alturaMax = 120;

  return html`
    <div class="flex items-end gap-2 h-36 px-2">
      ${dados.slice(-8).map((d, i) => html`
        <div key=${i} class="flex-1 flex flex-col items-center gap-0.5">
          <div class="w-full flex items-end gap-0.5 h-${alturaMax}">
            <div
              class="flex-1 bg-emerald-400 rounded-t opacity-80"
              style=${'height: ' + Math.max(2, (d.entradas / maxValor) * alturaMax) + 'px'}
              title=${'Entradas: ' + formatarMoeda(d.entradas)}
            ></div>
            <div
              class="flex-1 bg-red-400 rounded-t opacity-80"
              style=${'height: ' + Math.max(2, (d.saidas / maxValor) * alturaMax) + 'px'}
              title=${'Saídas: ' + formatarMoeda(d.saidas)}
            ></div>
          </div>
          <p class="text-xs text-gray-400 truncate w-full text-center">${d.period?.slice(5)}</p>
        </div>
      `)}
    </div>
    <div class="flex items-center gap-4 mt-3 justify-end">
      <span class="flex items-center gap-1 text-xs text-gray-500"><span class="w-3 h-3 bg-emerald-400 rounded inline-block"></span> Entradas</span>
      <span class="flex items-center gap-1 text-xs text-gray-500"><span class="w-3 h-3 bg-red-400 rounded inline-block"></span> Saídas</span>
    </div>
  `;
}

export default function DashboardPage() {
  const [dre, setDre] = useState(null);
  const [cashflow, setCashflow] = useState(null);
  const [transacoes, setTransacoes] = useState([]);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    async function carregar() {
      const start = inicioMes();
      const end = hoje();
      try {
        const [d, c, t] = await Promise.all([
          getDRE(start, end).catch(() => null),
          getCashFlow(start, end).catch(() => null),
          getTransactions({ inicio: start, fim: end, pagina: 1 }).catch(() => []),
        ]);
        setDre(d);
        setCashflow(c);
        setTransacoes(t?.slice(0, 5) || []);
      } finally {
        setCarregando(false);
      }
    }
    carregar();
  }, []);

  const lucroLiquido = dre?.lucro_liquido ?? 0;
  const variante = lucroLiquido > 0 ? 'positivo' : lucroLiquido < 0 ? 'negativo' : 'neutro';

  if (carregando) {
    return html`
      <div class="flex items-center justify-center h-64">
        <div class="w-8 h-8 border-4 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    `;
  }

  return html`
    <div class="p-6 max-w-6xl mx-auto space-y-6">
      <div>
        <h2 class="text-xl font-semibold text-gray-900">Dashboard</h2>
        <p class="text-sm text-gray-500">Resumo do mês atual</p>
      </div>

      <!-- Cards de resumo -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <${Card}
          titulo="Receita do mês"
          valor=${formatarMoeda(dre?.receita_bruta)}
          variante="positivo"
          subtitulo="Receita bruta"
        />
        <${Card}
          titulo="Despesas do mês"
          valor=${formatarMoeda((dre?.cmv || 0) + (dre?.total_despesas_operacionais || 0))}
          variante="negativo"
          subtitulo="CMV + operacionais"
        />
        <${Card}
          titulo="Lucro líquido"
          valor=${formatarMoeda(lucroLiquido)}
          variante=${variante}
          subtitulo=${'Margem: ' + (dre?.margem_liquida?.toFixed(1) || '0') + '%'}
        />
        <${Card}
          titulo="Saldo em caixa"
          valor=${formatarMoeda(cashflow?.saldo_final)}
          variante=${cashflow?.saldo_final >= 0 ? 'positivo' : 'negativo'}
          subtitulo="Saldo acumulado"
        />
      </div>

      <!-- Gráfico de barras -->
      <div class="bg-white rounded-xl border border-gray-200 p-5">
        <h3 class="text-sm font-semibold text-gray-700 mb-4">Entradas vs Saídas por semana</h3>
        <${GraficoBarras} dados=${cashflow?.entries || []} />
      </div>

      <!-- Últimas transações -->
      <div class="bg-white rounded-xl border border-gray-200 p-5">
        <h3 class="text-sm font-semibold text-gray-700 mb-4">Últimas transações</h3>
        ${transacoes.length === 0
          ? html`<p class="text-sm text-gray-400 text-center py-4">Nenhuma transação no período. <a href="#" class="text-brand-600 hover:underline">Faça um upload</a> para começar.</p>`
          : html`
            <div class="space-y-2">
              ${transacoes.map(t => html`
                <div key=${t.id} class="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                  <div class="flex-1 min-w-0 mr-4">
                    <p class="text-sm font-medium text-gray-800 truncate">${t.description}</p>
                    <p class="text-xs text-gray-400">${t.date} · ${t.category || 'Não categorizado'}</p>
                  </div>
                  <span class=${'text-sm font-semibold ' + (t.amount > 0 ? 'text-emerald-600' : 'text-red-600')}>
                    ${formatarMoeda(t.amount)}
                  </span>
                </div>
              `)}
            </div>
          `
        }
      </div>
    </div>
  `;
}
