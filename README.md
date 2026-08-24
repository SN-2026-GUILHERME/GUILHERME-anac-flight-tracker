# ANAC Flight Tracker

Painel de acompanhamento de voos programados, construído com dados públicos da
API do **SIROS/ANAC**, armazenados em um banco **Supabase** e exibidos em um
painel web estático publicado via **GitHub Pages**.

## Como funciona

1. Um workflow do **GitHub Actions** roda periodicamente (a cada 6 horas) e
   executa `scripts/fetch_flights.py`.
2. O script consulta a API pública do SIROS/ANAC
   (`https://sas.anac.gov.br/sas/siros_api/api/voos`) para os aeroportos
   configurados, filtra, remove duplicados e envia os registros para o
   Supabase.
3. O arquivo `index.html` consulta o Supabase diretamente do navegador
   (usando a chave pública `anon`) e exibe os voos em uma tabela, com filtro
   por aeroporto.

## Estrutura do projeto

```
anac-flight-tracker/
├── sql/
│   └── setup.sql              # Schema do banco (tabela, índices, RLS, policies)
├── scripts/
│   └── fetch_flights.py       # Busca os voos e envia ao Supabase
├── .github/workflows/
│   └── update-flights.yml     # Automação (roda o script periodicamente)
├── data/
│   └── airports.json          # Lista de aeroportos suportados
├── index.html                 # Painel web
└── README.md
```

## Configuração

### 1. Banco de dados (Supabase)

Rode o conteúdo de `sql/setup.sql` no **SQL Editor** do seu projeto Supabase.

### 2. Segredos do GitHub Actions

Em **Settings → Secrets and variables → Actions**, crie:

| Nome | Valor |
|---|---|
| `SUPABASE_URL` | URL do seu projeto (ex: `https://xxxx.supabase.co`) |
| `SUPABASE_SERVICE_KEY` | A **service_role key** (nunca a anon key) |

> A service_role key nunca deve ser commitada no código — ela concede acesso
> total ao banco. Ela só deve existir como GitHub Secret.

### 3. Painel (`index.html`)

Edite as constantes no topo do `<script>`:

```js
const SUPABASE_URL = "https://SEU-PROJETO.supabase.co";
const SUPABASE_ANON_KEY = "SUA_ANON_KEY_AQUI";
```

Aqui, use apenas a **anon/public key** — ela é segura para expor no
navegador, pois as permissões de leitura são controladas pelas políticas de
RLS definidas em `sql/setup.sql`.

### 4. Rodar manualmente (teste local)

```bash
SUPABASE_URL=https://SEU.supabase.co \
SUPABASE_SERVICE_KEY=SUAKEY \
AIRPORTS=SBCA \
python scripts/fetch_flights.py
```

## Aeroportos suportados

Consulte `data/airports.json` para a lista completa de códigos ICAO
disponíveis para filtro.

## Ambiente de desenvolvimento

Este projeto foi desenvolvido com o apoio de IA integrada ao GitHub, seguindo
o Guia do Aluno — Ambiente de Desenvolvimento Integrado (Programa SN-2026),
combinando duas trilhas de IA: GitHub Copilot (Trilha A) e Continue.dev com
Groq (Trilha E).
