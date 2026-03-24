/**
 * Página de Chat com o Agente Financeiro FinPME.
 * Streaming SSE + Tool Use via agentic loop no backend.
 */

import { html } from 'htm/preact';
import { useState, useRef, useEffect } from 'preact/hooks';
import { sendAgentMessage } from '../lib/api.js';

// ---------------------------------------------------------------------------
// Utilitários
// ---------------------------------------------------------------------------

/**
 * Renderização mínima de markdown: bold, itálico, código inline, listas e parágrafos.
 * Retorna HTML como string para uso com dangerouslySetInnerHTML.
 */
function markdownParaHtml(texto) {
  return texto
    // Cabeçalhos
    .replace(/^### (.+)$/gm, '<h3 class="font-bold text-base mt-3 mb-1">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="font-bold text-lg mt-3 mb-1">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 class="font-bold text-xl mt-3 mb-1">$1</h1>')
    // Negrito e itálico
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Código inline
    .replace(/`(.+?)`/g, '<code class="bg-gray-100 px-1 rounded text-sm font-mono">$1</code>')
    // Listas
    .replace(/^- (.+)$/gm, '<li class="ml-4 list-disc">$1</li>')
    .replace(/^(\d+)\. (.+)$/gm, '<li class="ml-4 list-decimal">$2</li>')
    // Linhas horizontais
    .replace(/^---$/gm, '<hr class="my-2 border-gray-200" />')
    // Quebras de linha duplas viram parágrafos
    .replace(/\n\n/g, '</p><p class="mb-2">')
    // Quebras simples
    .replace(/\n/g, '<br />');
}

const NOMES_FERRAMENTAS = {
  gerar_dre: 'Gerando DRE',
  gerar_fluxo_caixa: 'Gerando Fluxo de Caixa',
  buscar_transacoes: 'Buscando transações',
  resumo_periodo: 'Calculando resumo',
};

// ---------------------------------------------------------------------------
// Componentes de mensagem
// ---------------------------------------------------------------------------

function BolhaUsuario({ texto }) {
  return html`
    <div class="flex justify-end mb-4">
      <div class="max-w-[75%] bg-brand-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed shadow-sm">
        ${texto}
      </div>
    </div>
  `;
}

function BolhaAgente({ texto, ferramentas = [], carregando = false }) {
  return html`
    <div class="flex gap-3 mb-4">
      <!-- Avatar -->
      <div class="w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center flex-shrink-0 mt-1">
        <svg class="w-4 h-4 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17H3a2 2 0 01-2-2V5a2 2 0 012-2h14a2 2 0 012 2v10a2 2 0 01-2 2h-2" />
        </svg>
      </div>

      <div class="flex-1 max-w-[85%]">
        <!-- Indicadores de ferramentas -->
        ${ferramentas.length > 0 && html`
          <div class="mb-2 flex flex-wrap gap-2">
            ${ferramentas.map(f => html`
              <span key=${f} class="inline-flex items-center gap-1.5 text-xs bg-brand-50 text-brand-700 border border-brand-200 rounded-full px-3 py-1">
                <svg class="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"></path>
                </svg>
                ${NOMES_FERRAMENTAS[f] || f}
              </span>
            `)}
          </div>
        `}

        <!-- Texto da mensagem -->
        ${texto && html`
          <div
            class="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-gray-800 leading-relaxed shadow-sm prose-sm"
            dangerouslySetInnerHTML=${{ __html: '<p class="mb-2">' + markdownParaHtml(texto) + '</p>' }}
          />
        `}

        <!-- Cursor pulsante durante streaming -->
        ${carregando && !texto && html`
          <div class="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
            <span class="inline-flex gap-1">
              <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
              <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
              <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
            </span>
          </div>
        `}
      </div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Sugestões iniciais
// ---------------------------------------------------------------------------

const SUGESTOES = [
  'Gera o DRE deste mês pra mim',
  'Como está meu fluxo de caixa?',
  'Quais foram meus maiores gastos?',
  'Faz um resumo financeiro do último mês',
];

// ---------------------------------------------------------------------------
// Página principal
// ---------------------------------------------------------------------------

export default function ChatPage() {
  const [mensagens, setMensagens] = useState([]);
  const [input, setInput] = useState('');
  const [enviando, setEnviando] = useState(false);
  const finalRef = useRef(null);
  const inputRef = useRef(null);

  // Rola para o final quando novas mensagens chegam
  useEffect(() => {
    finalRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [mensagens]);

  async function enviar(textoOverride) {
    const texto = (textoOverride || input).trim();
    if (!texto || enviando) return;

    setInput('');
    setEnviando(true);

    // Adiciona mensagem do usuário ao histórico visual
    const novoHistorico = [...mensagens, { role: 'user', content: texto }];
    setMensagens(novoHistorico);

    // Prepara estado da mensagem do agente (vai ser preenchida via streaming)
    const idxAgente = novoHistorico.length;
    setMensagens(prev => [
      ...prev,
      { role: 'assistant', content: '', ferramentas: [], carregando: true },
    ]);

    try {
      // Histórico para enviar ao backend (só user/assistant com content string)
      const historicoApi = novoHistorico.map(m => ({
        role: m.role,
        content: m.content,
      }));

      await sendAgentMessage(
        historicoApi,
        // onChunk — texto chegando em tempo real
        (chunk) => {
          setMensagens(prev => {
            const copia = [...prev];
            copia[idxAgente] = {
              ...copia[idxAgente],
              content: copia[idxAgente].content + chunk,
              carregando: false,
            };
            return copia;
          });
        },
        // onToolStart — ferramenta sendo chamada
        (nomeFerramenta) => {
          setMensagens(prev => {
            const copia = [...prev];
            const ferramentas = copia[idxAgente].ferramentas || [];
            if (!ferramentas.includes(nomeFerramenta)) {
              copia[idxAgente] = {
                ...copia[idxAgente],
                ferramentas: [...ferramentas, nomeFerramenta],
                carregando: true,
              };
            }
            return copia;
          });
        },
        // onToolResult — ferramenta concluída (remove spinner)
        (nomeFerramenta) => {
          setMensagens(prev => {
            const copia = [...prev];
            copia[idxAgente] = {
              ...copia[idxAgente],
              ferramentas: (copia[idxAgente].ferramentas || []).filter(f => f !== nomeFerramenta),
            };
            return copia;
          });
        },
      );
    } catch (erro) {
      setMensagens(prev => {
        const copia = [...prev];
        copia[idxAgente] = {
          role: 'assistant',
          content: `Erro: ${erro.message}`,
          ferramentas: [],
          carregando: false,
        };
        return copia;
      });
    }

    setEnviando(false);
    inputRef.current?.focus();
  }

  function aoSubmeter(e) {
    e.preventDefault();
    enviar();
  }

  function aoTeclar(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      enviar();
    }
  }

  const semMensagens = mensagens.length === 0;

  return html`
    <div class="flex flex-col h-full overflow-hidden">
      <!-- Cabeçalho -->
      <div class="bg-white border-b border-gray-200 px-6 py-4 flex-shrink-0">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-full bg-brand-600 flex items-center justify-center">
            <svg class="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17H3a2 2 0 01-2-2V5a2 2 0 012-2h14a2 2 0 012 2v10a2 2 0 01-2 2h-2" />
            </svg>
          </div>
          <div>
            <h1 class="font-semibold text-gray-900 text-sm">Agente Financeiro</h1>
            <p class="text-xs text-gray-500">Peça relatórios, análises e insights em linguagem natural</p>
          </div>
        </div>
      </div>

      <!-- Área de mensagens -->
      <div class="flex-1 overflow-y-auto px-6 py-4">
        <!-- Estado vazio com sugestões -->
        ${semMensagens && html`
          <div class="flex flex-col items-center justify-center h-full text-center">
            <div class="w-16 h-16 rounded-full bg-brand-50 flex items-center justify-center mb-4">
              <svg class="w-8 h-8 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                  d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
              </svg>
            </div>
            <h2 class="text-lg font-semibold text-gray-900 mb-1">Como posso ajudar?</h2>
            <p class="text-sm text-gray-500 mb-6 max-w-sm">
              Pergunte sobre seus dados financeiros em linguagem natural.
              Posso gerar relatórios, analisar transações e muito mais.
            </p>
            <div class="grid grid-cols-2 gap-2 w-full max-w-md">
              ${SUGESTOES.map(s => html`
                <button
                  key=${s}
                  onClick=${() => enviar(s)}
                  class="text-left text-sm bg-white border border-gray-200 rounded-xl px-4 py-3 text-gray-700 hover:border-brand-300 hover:bg-brand-50 transition-colors"
                >
                  ${s}
                </button>
              `)}
            </div>
          </div>
        `}

        <!-- Mensagens -->
        ${mensagens.map((m, i) =>
          m.role === 'user'
            ? html`<${BolhaUsuario} key=${i} texto=${m.content} />`
            : html`<${BolhaAgente} key=${i} texto=${m.content} ferramentas=${m.ferramentas || []} carregando=${m.carregando} />`
        )}

        <div ref=${finalRef} />
      </div>

      <!-- Input -->
      <div class="bg-white border-t border-gray-200 px-4 py-3 flex-shrink-0">
        <form onSubmit=${aoSubmeter} class="flex gap-2 items-end">
          <textarea
            ref=${inputRef}
            value=${input}
            onInput=${(e) => setInput(e.target.value)}
            onKeyDown=${aoTeclar}
            placeholder="Pergunte algo sobre suas finanças… (Enter para enviar)"
            rows="1"
            disabled=${enviando}
            class="flex-1 resize-none border border-gray-300 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent disabled:opacity-50 max-h-32"
            style="min-height: 44px; overflow-y: auto;"
          />
          <button
            type="submit"
            disabled=${!input.trim() || enviando}
            class="w-10 h-10 bg-brand-600 text-white rounded-xl flex items-center justify-center hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex-shrink-0"
          >
            ${enviando
              ? html`<svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"></path>
                </svg>`
              : html`<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>`
            }
          </button>
        </form>
        <p class="text-xs text-gray-400 mt-1.5 text-center">
          Shift+Enter para nova linha · Enter para enviar
        </p>
      </div>
    </div>
  `;
}
