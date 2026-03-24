#!/bin/bash
# Gera frontend/env.js a partir das variáveis de ambiente.
# Usado pelo Cloudflare Pages no build step.
# Variáveis necessárias: SUPABASE_URL, SUPABASE_ANON_KEY, API_URL

set -e

REQUIRED_VARS=("SUPABASE_URL" "SUPABASE_ANON_KEY" "API_URL")
for VAR in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!VAR}" ]; then
    echo "❌ Variável de ambiente obrigatória não definida: $VAR"
    exit 1
  fi
done

cat > frontend/env.js <<EOF
window.__ENV__ = {
  SUPABASE_URL: '${SUPABASE_URL}',
  SUPABASE_ANON_KEY: '${SUPABASE_ANON_KEY}',
  API_URL: '${API_URL}',
};
EOF

echo "✅ frontend/env.js gerado com sucesso."
