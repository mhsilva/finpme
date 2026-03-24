/**
 * Roteador simples baseado em History API.
 * Mapeia URLs para componentes de página.
 */

const ouvintes = new Set();

export const router = {
  /** Retorna a rota atual baseada no pathname. */
  obterRota() {
    const path = window.location.pathname;
    return path === '/' ? '/dashboard' : path;
  },

  /** Navega para uma rota sem recarregar a página. */
  navegar(rota) {
    if (window.location.pathname !== rota) {
      window.history.pushState({}, '', rota);
    }
    ouvintes.forEach(fn => fn(rota));
  },

  /** Registra um ouvinte de mudança de rota. Retorna função para remover. */
  aoMudar(callback) {
    ouvintes.add(callback);

    // Escuta navegação pelo botão voltar/avançar do browser
    const aoPopState = () => callback(router.obterRota());
    window.addEventListener('popstate', aoPopState);

    return () => {
      ouvintes.delete(callback);
      window.removeEventListener('popstate', aoPopState);
    };
  },
};
