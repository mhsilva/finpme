/**
 * Cliente HTTP para o backend FinPME.
 * Adiciona JWT automaticamente em todas as requisições.
 */

import { getToken } from './auth.js';

const API_URL = window.__ENV__?.API_URL;

/**
 * Fetch com autenticação automática.
 * Lança erro se a resposta não for 2xx.
 */
async function apiFetch(endpoint, opcoes = {}) {
  const token = await getToken();

  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...opcoes.headers,
  };

  const resposta = await fetch(`${API_URL}${endpoint}`, {
    ...opcoes,
    headers,
  });

  if (!resposta.ok) {
    let mensagemErro = `Erro ${resposta.status}`;
    try {
      const corpo = await resposta.json();
      mensagemErro = corpo.detail || corpo.message || mensagemErro;
    } catch {
      // ignora erro de parse
    }
    throw new Error(mensagemErro);
  }

  if (resposta.status === 204) return null;
  return resposta.json();
}

// ---------------------------------------------------------------------------
// Transações
// ---------------------------------------------------------------------------

export function getTransactions(filtros = {}) {
  const params = new URLSearchParams();
  if (filtros.inicio)    params.set('inicio', filtros.inicio);
  if (filtros.fim)       params.set('fim', filtros.fim);
  if (filtros.categoria) params.set('categoria', filtros.categoria);
  if (filtros.tipo)      params.set('tipo', filtros.tipo);
  if (filtros.pagina)    params.set('pagina', filtros.pagina);
  const query = params.toString() ? `?${params}` : '';
  return apiFetch(`/transactions${query}`);
}

export function updateTransaction(id, dados) {
  return apiFetch(`/transactions/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(dados),
  });
}

export function deleteTransaction(id) {
  return apiFetch(`/transactions/${id}`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// Upload
// ---------------------------------------------------------------------------

export async function uploadFile(arquivo) {
  const token = await getToken();
  const formData = new FormData();
  formData.append('file', arquivo);

  const resposta = await fetch(`${API_URL}/upload`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });

  if (!resposta.ok) {
    const corpo = await resposta.json().catch(() => ({}));
    throw new Error(corpo.detail || 'Erro ao enviar arquivo');
  }
  return resposta.json();
}

export function getUploadStatus(fileId) {
  return apiFetch(`/upload/status/${fileId}`);
}

export function getUploads() {
  return apiFetch('/upload');
}

// ---------------------------------------------------------------------------
// Relatórios
// ---------------------------------------------------------------------------

export function getDRE(start, end) {
  return apiFetch(`/reports/dre?start=${start}&end=${end}`);
}

export function getCashFlow(start, end) {
  return apiFetch(`/reports/cashflow?start=${start}&end=${end}`);
}

// ---------------------------------------------------------------------------
// Chat IA
// ---------------------------------------------------------------------------

export function sendChatMessage(message, context = {}) {
  return apiFetch('/ai/chat', {
    method: 'POST',
    body: JSON.stringify({ message, context }),
  });
}

/**
 * Envia mensagens para o agente com streaming SSE.
 * @param {Array}    messages      - Histórico [{role, content}, ...]
 * @param {Function} onChunk       - Chamado com cada fragmento de texto
 * @param {Function} onToolStart   - Chamado quando uma ferramenta começa (nome)
 * @param {Function} onToolResult  - Chamado quando ferramenta termina (nome, result)
 */
export async function sendAgentMessage(messages, onChunk, onToolStart, onToolResult) {
  const token = await getToken();

  const resposta = await fetch(`${API_URL}/ai/agent`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ messages }),
  });

  if (!resposta.ok) {
    const corpo = await resposta.json().catch(() => ({}));
    throw new Error(corpo.detail || `Erro ${resposta.status}`);
  }

  const reader = resposta.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const linhas = buffer.split('\n');
    buffer = linhas.pop(); // mantém linha incompleta no buffer

    for (const linha of linhas) {
      if (!linha.startsWith('data: ')) continue;
      try {
        const evento = JSON.parse(linha.slice(6));
        if (evento.type === 'text')        onChunk?.(evento.content);
        else if (evento.type === 'tool_start')  onToolStart?.(evento.name);
        else if (evento.type === 'tool_result') onToolResult?.(evento.name, evento.result);
        else if (evento.type === 'error')  throw new Error(evento.message);
      } catch (e) {
        if (e.message && !e.message.startsWith('JSON')) throw e;
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Financeiro — Contas a Pagar/Receber
// ---------------------------------------------------------------------------

export function getContas(filtros = {}) {
  const params = new URLSearchParams();
  if (filtros.type)   params.set('type', filtros.type);
  if (filtros.status) params.set('status', filtros.status);
  if (filtros.inicio) params.set('inicio', filtros.inicio);
  if (filtros.fim)    params.set('fim', filtros.fim);
  const q = params.toString() ? `?${params}` : '';
  return apiFetch(`/financeiro/contas${q}`);
}

export function getResumoContas() {
  return apiFetch('/financeiro/contas/resumo');
}

export function createConta(dados) {
  return apiFetch('/financeiro/contas', {
    method: 'POST',
    body: JSON.stringify(dados),
  });
}

export function updateConta(id, dados) {
  return apiFetch(`/financeiro/contas/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(dados),
  });
}

export function pagarConta(id, opcoes = {}) {
  const params = new URLSearchParams();
  if (opcoes.paid_date)      params.set('paid_date', opcoes.paid_date);
  if (opcoes.transaction_id) params.set('transaction_id', opcoes.transaction_id);
  if (opcoes.valor_pago)     params.set('valor_pago', opcoes.valor_pago);
  const q = params.toString() ? `?${params}` : '';
  return apiFetch(`/financeiro/contas/${id}/pagar${q}`, { method: 'POST' });
}

export function cancelarConta(id, todasParcelas = false) {
  const q = todasParcelas ? '?todas_parcelas=true' : '';
  return apiFetch(`/financeiro/contas/${id}${q}`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// Financeiro — Conciliação Bancária
// ---------------------------------------------------------------------------

export function getConciliacaoStats() {
  return apiFetch('/financeiro/conciliacao/stats');
}

export function getConciliacaoPendentes(filtros = {}) {
  const params = new URLSearchParams();
  if (filtros.inicio) params.set('inicio', filtros.inicio);
  if (filtros.fim)    params.set('fim', filtros.fim);
  const q = params.toString() ? `?${params}` : '';
  return apiFetch(`/financeiro/conciliacao/pendentes${q}`);
}

export function getConciliacaoSugestoes(filtros = {}) {
  const params = new URLSearchParams();
  if (filtros.transaction_id) params.set('transaction_id', filtros.transaction_id);
  if (filtros.score_min)      params.set('score_min', filtros.score_min);
  const q = params.toString() ? `?${params}` : '';
  return apiFetch(`/financeiro/conciliacao/sugestoes${q}`);
}

export function confirmarConciliacao(transactionId, payableReceivableId) {
  return apiFetch(
    `/financeiro/conciliacao/confirmar?transaction_id=${transactionId}&payable_receivable_id=${payableReceivableId}`,
    { method: 'POST' },
  );
}

export function autoConciliar(scoreMin = 0.80) {
  return apiFetch(`/financeiro/conciliacao/auto?score_min=${scoreMin}`, { method: 'POST' });
}

export function desfazerConciliacao(matchId) {
  return apiFetch(`/financeiro/conciliacao/${matchId}`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// Financeiro — Contas Bancárias
// ---------------------------------------------------------------------------

export function getContasBancarias() {
  return apiFetch('/financeiro/contas-bancarias');
}

export function createContaBancaria(dados) {
  return apiFetch('/financeiro/contas-bancarias', {
    method: 'POST',
    body: JSON.stringify(dados),
  });
}

export function updateContaBancaria(id, dados) {
  return apiFetch(`/financeiro/contas-bancarias/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(dados),
  });
}

export function deleteContaBancaria(id) {
  return apiFetch(`/financeiro/contas-bancarias/${id}`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// Financeiro — Centros de Custo
// ---------------------------------------------------------------------------

export function getCentrosCusto() {
  return apiFetch('/financeiro/centros-custo');
}

export function createCentroCusto(dados) {
  return apiFetch('/financeiro/centros-custo', {
    method: 'POST',
    body: JSON.stringify(dados),
  });
}

export function updateCentroCusto(id, dados) {
  return apiFetch(`/financeiro/centros-custo/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(dados),
  });
}

export function deleteCentroCusto(id) {
  return apiFetch(`/financeiro/centros-custo/${id}`, { method: 'DELETE' });
}

export function getRelatorioCentroCusto(id, inicio, fim) {
  return apiFetch(`/financeiro/centros-custo/${id}/relatorio?inicio=${inicio}&fim=${fim}`);
}

export function alocarTransacaoCentroCusto(transactionId, costCenterId, percentage = 100) {
  return apiFetch(
    `/financeiro/centros-custo/transacao/${transactionId}?cost_center_id=${costCenterId}&percentage=${percentage}`,
    { method: 'POST' },
  );
}

export function removerAlocacaoCentroCusto(transactionId) {
  return apiFetch(`/financeiro/centros-custo/transacao/${transactionId}`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export function getMe() {
  return apiFetch('/auth/me');
}
