/**
 * Página de Upload de Arquivos.
 * Drag-and-drop para OFX, XML, CSV, PDF e imagens com polling de status.
 * Arquivos PDF e imagens são processados via Claude (parse inteligente).
 */

import { useState, useEffect, useRef } from 'preact/hooks';
import { html } from 'htm/preact';
import { uploadFile, getUploads, getUploadStatus } from '../lib/api.js';

const STATUS_LABELS = {
  pending:    { texto: 'Aguardando',   cor: 'bg-yellow-100 text-yellow-700' },
  processing: { texto: 'Processando',  cor: 'bg-blue-100 text-blue-700' },
  done:       { texto: 'Concluído',    cor: 'bg-emerald-100 text-emerald-700' },
  error:      { texto: 'Erro',         cor: 'bg-red-100 text-red-700' },
};

function BadgeStatus({ status }) {
  const cfg = STATUS_LABELS[status] || STATUS_LABELS.pending;
  return html`<span class=${'text-xs font-medium px-2 py-0.5 rounded-full ' + cfg.cor}>${cfg.texto}</span>`;
}

export default function UploadPage() {
  const [arquivos, setArquivos] = useState([]);      // uploads existentes
  const [enviando, setEnviando] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [erro, setErro] = useState('');
  const [sucesso, setSucesso] = useState('');
  const inputRef = useRef(null);
  const pollingRef = useRef(null);

  useEffect(() => {
    carregarUploads();
    return () => clearInterval(pollingRef.current);
  }, []);

  async function carregarUploads() {
    try {
      const lista = await getUploads();
      setArquivos(lista);

      // Inicia polling se houver arquivos pendentes/processando
      const temPendentes = lista.some(a => a.status === 'pending' || a.status === 'processing');
      if (temPendentes) {
        clearInterval(pollingRef.current);
        pollingRef.current = setInterval(carregarUploads, 3000);
      } else {
        clearInterval(pollingRef.current);
      }
    } catch {
      // silencia erros de rede
    }
  }

  async function processar(arquivo) {
    const ext = arquivo.name.split('.').pop().toLowerCase();
    if (!['ofx', 'xml', 'csv', 'pdf', 'png', 'jpg', 'jpeg', 'webp'].includes(ext)) {
      setErro(`Tipo de arquivo não suportado: .${ext}. Use OFX, CSV, XML NF-e, PDF ou imagem.`);
      return;
    }

    setErro('');
    setSucesso('');
    setEnviando(true);

    try {
      await uploadFile(arquivo);
      setSucesso(`"${arquivo.name}" enviado com sucesso! O processamento começará em instantes.`);
      await carregarUploads();
    } catch (err) {
      setErro(err.message || 'Erro ao enviar arquivo.');
    } finally {
      setEnviando(false);
    }
  }

  function onArquivosSelecionados(e) {
    const files = Array.from(e.target.files || []);
    files.forEach(processar);
    if (inputRef.current) inputRef.current.value = '';
  }

  function onDrop(e) {
    e.preventDefault();
    setDragging(false);
    const files = Array.from(e.dataTransfer.files || []);
    files.forEach(processar);
  }

  function formatarData(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('pt-BR');
  }

  return html`
    <div class="p-6 max-w-3xl mx-auto space-y-6">
      <div>
        <h2 class="text-xl font-semibold text-gray-900">Upload de Documentos Financeiros</h2>
        <p class="text-sm text-gray-500">Envie extratos, notas fiscais, boletos ou recibos — a IA identifica e processa automaticamente</p>
      </div>

      <!-- Mensagens de feedback -->
      ${erro && html`
        <div class="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm flex items-start gap-2">
          <span class="mt-0.5">⚠</span>
          <span>${erro}</span>
        </div>
      `}
      ${sucesso && html`
        <div class="bg-emerald-50 border border-emerald-200 text-emerald-700 rounded-lg px-4 py-3 text-sm flex items-start gap-2">
          <span class="mt-0.5">✓</span>
          <span>${sucesso}</span>
        </div>
      `}

      <!-- Área de drag-and-drop -->
      <div
        class=${'border-2 border-dashed rounded-xl p-10 text-center transition-colors cursor-pointer ' +
          (dragging ? 'border-brand-500 bg-brand-50' : 'border-gray-300 hover:border-brand-400 hover:bg-gray-50')}
        onDragOver=${(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave=${() => setDragging(false)}
        onDrop=${onDrop}
        onClick=${() => inputRef.current?.click()}
      >
        <input
          ref=${inputRef}
          type="file"
          class="hidden"
          accept=".ofx,.xml,.csv,.pdf,.png,.jpg,.jpeg,.webp"
          multiple
          onChange=${onArquivosSelecionados}
        />

        ${enviando
          ? html`
            <div class="w-10 h-10 border-4 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
            <p class="text-sm text-gray-500">Enviando arquivo...</p>
          `
          : html`
            <svg xmlns="http://www.w3.org/2000/svg" class="w-12 h-12 text-gray-300 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
            <p class="text-sm font-medium text-gray-700">Arraste arquivos aqui ou <span class="text-brand-600">clique para selecionar</span></p>
            <p class="text-xs text-gray-400 mt-1">OFX · CSV · XML NF-e · PDF · PNG · JPG — múltiplos arquivos aceitos</p>
          `
        }
      </div>

      <!-- Lista de uploads -->
      ${arquivos.length > 0 && html`
        <div class="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div class="px-5 py-3 border-b border-gray-100">
            <h3 class="text-sm font-semibold text-gray-700">Uploads recentes</h3>
          </div>
          <div class="divide-y divide-gray-100">
            ${arquivos.map(a => html`
              <div key=${a.id} class="flex items-center justify-between px-5 py-3">
                <div class="flex-1 min-w-0 mr-4">
                  <p class="text-sm font-medium text-gray-800 truncate">${a.filename}</p>
                  <p class="text-xs text-gray-400">
                    ${a.file_type?.toUpperCase()} · Enviado em ${formatarData(a.created_at)}
                    ${a.processed_at ? ` · Processado em ${formatarData(a.processed_at)}` : ''}
                  </p>
                </div>
                <${BadgeStatus} status=${a.status} />
              </div>
            `)}
          </div>
        </div>
      `}
    </div>
  `;
}
