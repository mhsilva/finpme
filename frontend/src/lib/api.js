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

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export function getMe() {
  return apiFetch('/auth/me');
}
