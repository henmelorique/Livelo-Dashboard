# Painel de Pontos — parceiros Livelo

Dashboard em Flask que lê a lista de parceiros da Livelo
(`livelo.com.br/juntar-pontos/todos-os-parceiros`), guarda um histórico
diário de pontuação e mostra tudo num painel web com:

- Tabela de parceiros ordenável por **nome**, **pontuação atual**,
  **variação %** e **data da última verificação**.
- Sinalização de **promoção** (comparando com o "Eram X pontos" que a
  própria Livelo exibe) e de **parceiro novo**.
- Busca por nome e filtro "só promoções".
- Página de **histórico por parceiro** com gráfico de linhas (Chart.js) e
  seletor de período (7/30/90/365 dias, "tudo" ou intervalo customizado).

## Os dois modos do projeto

| | `full` (local) | `readonly` (produção/deploy grátis) |
|---|---|---|
| Quem faz o scraping | O próprio app, direto na Livelo | O GitHub Actions, 1x/dia |
| Onde os dados ficam | `instance/livelo.db` (SQLite local) | `data/livelo_export.json`, publicado no seu repositório GitHub |
| Como o app pega os dados | Consulta o SQLite diretamente | Baixa o JSON de `raw.githubusercontent.com` e importa num SQLite local |
| Quando usar | Rodando na sua máquina | Hospedado (ex.: PythonAnywhere free) |

Isso existe porque hospedagens gratuitas normalmente não te dão as duas
coisas de que esse projeto precisa ao mesmo tempo: **acesso livre à
internet** (para o scraping) e **disco persistente** (para o histórico não
sumir a cada deploy). Separando as duas responsabilidades, cada parte roda
onde é de graça e funciona bem:

```
GitHub Actions (1x/dia, grátis, internet livre)
        │  scrapa livelo.com.br
        ▼
   commita data/livelo_export.json no repositório GitHub
        │  raw.githubusercontent.com (liberado até no free tier)
        ▼
PythonAnywhere free (hospeda o dashboard, modo readonly)
```

## 1. Rodar localmente (modo `full`)

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Abra **http://127.0.0.1:5000**. Na primeira execução o banco está vazio,
então o app dispara uma coleta em background assim que sobe. Depois disso
roda 1x/dia (por padrão 07:00 local; ajustável com `LIVELO_SCRAPE_HOUR`).
O botão **"↻ Atualizar agora"** força uma coleta manual a qualquer momento.

## 2. Publicar no GitHub (necessário para o deploy grátis)

```bash
cd livelo_dashboard
git init
git add .
git commit -m "Painel de Pontos Livelo"
gh repo create livelo-dashboard --private --source=. --push
# (ou crie o repo pelo site do GitHub e faça `git remote add origin ...` + `git push`)
```

O workflow em `.github/workflows/daily_scrape.yml` já está configurado para
rodar todo dia às 07:00 (horário de Brasília) automaticamente assim que o
repositório existir no GitHub — não precisa configurar nada a mais. Você
pode testar na hora: aba **Actions** do repositório → **Coleta diária de
pontos Livelo** → **Run workflow**. Depois de rodar, confira se
`data/livelo_export.json` foi criado/commitado no repo.

## 3. Hospedar o dashboard de graça na PythonAnywhere

1. Crie uma conta grátis em [pythonanywhere.com](https://www.pythonanywhere.com)
   (plano **Beginner**, sem cartão de crédito).
2. Abra um **Bash console** (aba **Consoles**) e clone o seu repositório:
   ```bash
   git clone https://github.com/SEU_USUARIO/livelo-dashboard.git
   cd livelo-dashboard
   mkvirtualenv --python=python3.12 livelo-venv
   pip install -r requirements.txt
   ```
3. Vá na aba **Web** → **Add a new web app** → **Manual configuration** →
   escolha a versão do Python compatível → aponte o **Virtualenv** para
   `/home/SEU_USUARIO/.virtualenvs/livelo-venv`.
4. Ainda na aba **Web**, clique no link do **arquivo WSGI** (algo como
   `/var/www/seuusuario_pythonanywhere_com_wsgi.py`) e substitua o
   conteúdo por:
   ```python
   import sys, os

   project_home = '/home/SEU_USUARIO/livelo-dashboard'
   if project_home not in sys.path:
       sys.path.insert(0, project_home)

   os.environ['LIVELO_MODE'] = 'readonly'
   os.environ['LIVELO_DB_PATH'] = project_home + '/instance/livelo.db'
   os.environ['LIVELO_GITHUB_DATA_URL'] = (
       'https://raw.githubusercontent.com/SEU_USUARIO/livelo-dashboard/main/data/livelo_export.json'
   )

   from app import app as application
   ```
5. Clique em **Reload** na aba Web. Pronto — seu painel está no ar em
   `https://seuusuario.pythonanywhere.com`.

Nesse modo, o app **nunca** acessa `livelo.com.br` diretamente (o que não
funcionaria mesmo, já que o plano grátis só libera uma lista de sites
específicos). Ele sincroniza a partir do JSON publicado no seu repositório
— e `raw.githubusercontent.com` está nessa lista de sites liberados, então
funciona sem pedir nenhuma liberação especial.

### Como os dados chegam até o site publicado

- Ao iniciar (toda vez que a PythonAnywhere reinicia o processo), o app
  sincroniza automaticamente em background.
- O botão **"↻ Sincronizar do GitHub"** no topo do painel também dispara
  essa sincronização manualmente a qualquer momento — útil porque, sem
  Tarefas Agendadas no plano grátis, esse pull sob demanda é o que garante
  que você sempre vê os dados mais recentes quando abre o painel.

### ⚠️ Sobre o plano gratuito da PythonAnywhere (atualizado)

Desde janeiro de 2026, contas gratuitas **novas** não têm mais direito a
Tarefas Agendadas (isso virou exclusivo do plano pago) — por isso o projeto
foi desenhado para **não depender delas**: quem faz a coleta é sempre o
GitHub Actions. Além disso:
- Apps gratuitos da PythonAnywhere **expiram após 1 mês sem login** — a
  PythonAnywhere avisa por e-mail antes disso acontecer; basta entrar na
  conta e clicar para renovar.
- O limite de CPU do plano grátis (100 seg/dia) é tranquilo para esse uso,
  já que o app só faz requisições leves de leitura, nunca o scraping
  pesado em si.

## Alternativas de hospedagem (se quiser fugir dessa combinação)

| Opção | Prós | Contras para este projeto |
|---|---|---|
| **PythonAnywhere free + GitHub Actions** (recomendado acima) | 100% grátis, sem cartão | Um pouco mais de configuração inicial |
| **Render (free web service)** | Deploy simples via Git, sem whitelist | Disco é apagado a cada deploy/reinício — precisaria do mesmo modo `readonly` para não depender de disco |
| **Railway / Fly.io / VPS pequena** | Sem limitações de whitelist ou disco | A partir de ~US$5/mês |

Se preferir Render no lugar da PythonAnywhere, o mesmo modo `readonly`
funciona lá também (é só configurar as mesmas variáveis de ambiente) — a
única diferença é que o Render não tem restrição de whitelist, então essa
combinação com GitHub Actions vira só uma opção a mais de robustez, não uma
necessidade.

## Como funciona o scraper (`scraper.py`)

A página de parceiros lista cada loja num card (`<a>`) contendo o selo
**"Promoção"**/**"Nova"** (quando existe), o nome do parceiro (no `alt` da
logo), a pontuação atual e, quando há promoção, o valor anterior ("Eram X
pontos"). O `scraper.py`:

1. Baixa o HTML com `requests` (com um User-Agent de navegador).
2. Localiza todos os links de parceiro (`/juntar-pontos/parceiros/...`).
3. Extrai o nome do `alt` da imagem da logo (`alt="Logo {Nome}"`).
4. Faz o parsing do texto de cada card com uma regex tolerante a variações
   de espaçamento, tanto para a pontuação padrão quanto para a faixa
   "Clube Livelo" (quando o parceiro tem um valor extra para assinantes).
5. Se a Livelo mudar o layout e passar a montar a lista via JavaScript no
   cliente (o scraper simples passar a retornar 0 parceiros), há um
   fallback opcional com **Playwright** — descomente a linha no
   `requirements.txt`, rode `playwright install chromium`, e
   `scrape_partners()` tenta esse caminho automaticamente.

**Importante:** como qualquer scraper, isso pode quebrar se a Livelo mudar
o HTML da página. Se a coleta parar de funcionar (o workflow do GitHub
Actions vai falhar e você recebe um e-mail do próprio GitHub avisando),
rode `python scraper.py` direto no terminal para ver o que está sendo
capturado e ajustar a regex em `CARD_RE` / `_extract_name` conforme
necessário.

## Estrutura do projeto

```
livelo_dashboard/
├── app.py                    # rotas Flask (modo full E readonly)
├── config.py                  # LIVELO_MODE, caminhos, URL do GitHub
├── scraper.py                  # baixa e faz parsing da página de parceiros
├── ingest.py                    # roda o scraper e grava no banco local (modo full)
├── data_export.py                # exporta/importa snapshot completo em JSON
├── remote_sync.py                 # busca o snapshot no GitHub (modo readonly)
├── models.py                       # SQLAlchemy: Partner, PointsHistory, ScrapeLog
├── scripts/
│   └── run_scrape_and_export.py     # rodado pelo GitHub Actions
├── .github/workflows/
│   └── daily_scrape.yml               # agenda a coleta diária
├── requirements.txt
├── templates/                          # HTML (Jinja2)
├── static/css, static/js                # estilo e front-end
├── data/
│   └── livelo_export.json                 # gerado automaticamente, versionado no git
└── instance/
    └── livelo.db                            # SQLite local, NÃO versionado (está no .gitignore)
```

## Endpoints da API

| Rota | Descrição |
|---|---|
| `GET /api/partners?sort=name\|points\|variation\|updated&order=asc\|desc&promo_only=true&q=texto` | Lista de parceiros com estado atual |
| `GET /api/partner/<slug>/history?days=30` ou `?start=YYYY-MM-DDTHH:MM:SS&end=...` | Histórico de um parceiro |
| `POST /api/refresh` | Modo full: coleta manual. Modo readonly: sincroniza do GitHub |
| `GET /api/status` | Status da última coleta/sincronização + modo atual |

## Métricas incluídas além do pedido

- **% de variação** em relação ao valor "normal" anterior (`Eram X pontos`).
- **Pontuação Clube Livelo**, quando o parceiro tem uma faixa extra para
  assinantes (linha pontilhada no gráfico).
- **Selo "Nova"** para parceiros que apareceram pela primeira vez na lista.
- **"Ticker tape"** no topo com as maiores promoções do momento.
- **Log de execuções do scraper** (`ScrapeLog`) para diagnosticar falhas.

## Limitações conhecidas

- O scraper depende da estrutura atual do HTML da Livelo.
- No modo `readonly`, os dados só ficam tão atualizados quanto a última
  execução do GitHub Actions + a última vez que alguém (ou o próprio
  processo ao iniciar) sincronizou — não é tempo real.
- `data/livelo_export.json` cresce um pouco a cada dia (mais histórico).
  Para um projeto pessoal isso é tranquilo por bastante tempo; se um dia
  ficar grande demais para o gosto, dá para trocar por uma janela de
  retenção (ex.: manter só os últimos 2 anos) sem mudar o resto do design.
