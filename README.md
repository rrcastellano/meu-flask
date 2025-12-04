# EVChargeLog.com
#### Video Demo: **** INSERT VIDEO URL HERE ****
#### Description:

**EVChargeLog.com** is a web application that helps electric vehicle owners record, manage, and analyze their charging sessions. Users can log each recharge with date, kWh, cost, whether it was free/covered ("isento"), odometer reading, location, and notes. A dashboard summarizes KPIs, reveals monthly trends, and estimates savings versus gasoline based on user-provided settings. The project was built with **Python, Flask, SQLite, HTML/CSS, and JavaScript**, emphasizing authentication, internationalization, robust CSV import/export, and a practical REST layer to manage data.

From the user’s perspective, the flow is simple: register and sign in, add charges individually or in bulk (CSV), configure gasoline price and average consumption (km/l), and explore the Dashboard for insights. Behind the scenes, EVChargeLog.com aggregates monthly data, derives kilometers from odometer entries, computes consumption per 100 km, cost per kWh and per km, and shows savings estimates when settings are available.

---

##### Key Features
- **Authentication & sessions (Flask-Login):** secure login/registration/logout and protection of data routes such as `/dashboard`, `/recharge`, `/bulk_recharge`, `/account`, and `/manage_recharges`.
- **Internationalization (Flask-Babel):** support for `pt_BR`, `en`, and `es` with a locale selector that honors session, user preference (optional), and browser headers. Translation helpers (`_` and `_l`) are injected into all templates.
- **Secure forms (WTForms + CSRFProtect):** validated forms for login/registration, per-charge entry, bulk CSV import, account settings, and contact; numeric fields enforce positive values and sensible ranges.
- **Recharge management (REST):** GET list with pagination, filtering, and sorting; PATCH for inline editing; DELETE for removal—restricted by `user_id` checks.
- **Robust CSV import:** tolerant to encodings (UTF-8/Latin-1), BOM removal, newline normalization, and automatic delimiter detection; strict header validation and safe parsing.
- **CSV export:** filtered or complete datasets, served as downloadable files.
- **Dashboard with KPIs and trends:** monthly aggregation (cost totals, payments vs. free sessions, kWh, derived km, consumption/100 km), plus savings estimates using gasoline settings.
- **Chart data APIs:** `/api/recharges` and `/api/recharges/monthly` return ready-to-plot series consumed by front-end JavaScript (Chart.js in `templates/partials/dashboard_charts.js`).
- **Currency filters:** custom Jinja filters `brl` and `usd` format values for display.
- **Contact form & logging:** messages logged to SQLite and wired for SMTP via Flask-Mail, with environment-based credentials.

---

##### Architecture & Design Decisions
- **Framework choice:** Flask offers lightweight routing, template rendering, and smooth integration with Flask-Login, Babel, WTForms, and CSRF protection.
- **Data model:** SQLite was chosen for portability. Tables include `users` (auth), `recharges` (charge records), `settings` (gasoline price and average km/l), and `contact_logs` (messages).
- **Internationalization first:** a `locale_selector` is used to consistently pick language, while form labels/messages are marked for translation. This makes the UI coherent across English, Portuguese, and Spanish.
- **Security:** CSRF is enabled globally; server-side validations ensure numeric inputs (kWh, cost, odometer) are safe; REST endpoints check ownership before updates or deletes.
- **Derived metrics:** monthly km is derived from odometer min/max per month (with fallbacks when only one reading exists); consumption per 100 km and costs per kWh/km are computed server-side to keep front-end logic minimal.
- **Naming conventions:** the project uses “recharge”/“recarga” consistently to avoid ambiguity with mobile “top-up” terminology.
- **Front-end charts:** APIs deliver arrays of labels and values tailored for Chart.js, keeping the dashboard responsive and decoupled from database specifics.
- **Import tolerance:** the CSV validator sanitizes problematic files (BOM, nulls, mixed newlines) and tries common delimiters (comma, semicolon, tab), reducing friction when consolidating historical data.

---

##### File Structure
```
EVChargeLog.com/
│
├── app.py                          # Flask app: routes, auth, i18n, forms, APIs, CSV export, filters, contact
├── babel.cfg                       # Flask-Babel configuration
├── dados em branco.db              # SQLite DB (empty template)
├── dados.db                        # SQLite DB with sample/content
├── estrutura.txt                   # Project structure notes
├── Procfile                        # web: gunicorn app:app (deployment)
├── requirements.txt                # Dependencies (Flask, Flask-Login, Werkzeug, WTForms, email-validator, gunicorn)
├── schema.sql                      # Database schema
│
├── static/
│   │
│   ├── styles.css                  # Base styles
│   ├── styles-dark.css             # Dark theme (migration target)
│   ├── manage_recharges.js         # Front-end logic for management tables
│   │
│   └── img/
│       │
│       ├── favicon-16x16.png       # 16x16 icon
│       ├── favicon-32x32.png       # 32x32 icon
│       ├── favicon-48x48.png       # 48x48 icon
│       ├── favicon-64x64.png       # 64x64 icon
│       ├── favicon-128x128.png     # 128x128 icon
│       ├── favicon-256x256.png     # 256x256 icon
│       ├── logo.png                # PNG logo
│       ├── logo.svg                # SVG logo
│       └── favicon.ico             # ICO logo
│
├── templates/
│   │
│   ├── account.html                # Account settings
│   ├── bulk_recharge.html          # CSV import for recharges
│   ├── contact.html                # Contact page
│   ├── dashboard.html              # Main dashboard with visualizations
│   ├── index.html                  # Login page
│   ├── layout.html                 # Base layout for all pages
│   ├── recharge.html               # Single recharge form
│   ├── register.html               # User registration
│   ├── manage_recharges.html       # Edit/manage all recharges
│   │
│   └── partials/
│       │
│       └── dashboard_charts.js     # JS that builds charts in the dashboard
│
└── translations/locales/
    │
    ├── en/LC_MESSAGES/
    │   │
    │   ├── messages.mo             # English compiled translations
    │   └── messages.po             # English source translations
    │
    ├── es/LC_MESSAGES/
    │   │
    │   ├── messages.mo             # Spanish compiled translations
    │   └── messages.po             # Spanish source translations
    │
    └── pt_BR/LC_MESSAGES/
        │
        ├── messages.mo             # Portuguese compiled translations
        └── messages.po             # Portuguese source translations
```

---

##### Installation & Running
1. **Create & activate a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # macOS/Linux
   .venv\Scripts\activate     # Windows
   ```
2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
3. **Environment variables** (examples)
   ```bash
   export SECRET_KEY="a_secure_random_key"
   export MAIL_USERNAME="your_email@gmail.com"
   export MAIL_PASSWORD="your_app_password"
   ```
4. **Initialize the database** (if needed)
   ```bash
   sqlite3 dados.db < schema.sql
   ```
5. **Run the app**
   ```bash
   python app.py
   # or
   flask run
   ```

For deployment on platforms that use a **Procfile**, the process command is typically `web: gunicorn app:app`.

---

##### Usage Flow
- **Register / Login** → access the **Dashboard** with KPIs and charts.
- **Single Recharge** (`/recharge`) → validated form entry.
- **Bulk Import** (`/bulk_recharge`) → robust CSV ingestion with feedback.
- **Settings** (`/account`) → gasoline price & average km/l for savings estimation.
- **Manage** (`/manage_recharges`) → list/filter/edit/delete via REST endpoints.
- **Export CSV** (`/export_recharges`) → honors current filters.
- **Contact** (`/contact`) → message logging to `contact_logs`.

---

##### Future Work
- Role-based authorization (admin/user) and change auditing.
- Integrations with public EV charging providers.
- Automated tests (unit/integration) and CI/CD.
- Caching for monthly aggregations and chart endpoints.


---

## Tradução (Português)
#### Video Demo: **** INSERIR URL DO VIDEO AQUI ****
#### Descrição:

**EVChargeLog.com** é um aplicativo web que ajuda proprietários de veículos elétricos a registrar, gerenciar e analisar suas recargas. O usuário lança cada recarga com data, kWh, custo, se foi isenta/coberta ("isento"), odômetro, local e observações. Um dashboard resume KPIs, revela tendências mensais e estima economia em relação à gasolina com base nas configurações do usuário. O projeto foi construído com **Python, Flask, SQLite, HTML/CSS e JavaScript**, enfatizando autenticação, internacionalização, importação/exportação de CSV robusta e uma camada REST prática para gerenciar dados.

Do ponto de vista do usuário, o fluxo é direto: registrar‑se e entrar, adicionar recargas individualmente ou em lote (CSV), configurar preço da gasolina e consumo médio (km/l) e explorar o Dashboard em busca de insights. Nos bastidores, o EVChargeLog.com agrega dados mensais, deriva quilômetros a partir dos odômetros, calcula consumo por 100 km, custo por kWh e por km e exibe estimativas de economia quando há configurações disponíveis.

---

##### Funcionalidades
- **Autenticação e sessão (Flask-Login):** login/registro/logout seguros e proteção de rotas como `/dashboard`, `/recharge`, `/bulk_recharge`, `/account` e `/manage_recharges`.
- **Internacionalização (Flask-Babel):** suporte a `pt_BR`, `en` e `es` com seletor de locale que respeita sessão, preferência do usuário (opcional) e headers do navegador. As funções de tradução (`_` e `_l`) são injetadas nos templates.
- **Formulários seguros (WTForms + CSRFProtect):** formulários validados para login/registro, recarga individual, importação CSV, configurações e contato; campos numéricos exigem valores positivos e limites razoáveis.
- **Gestão de recargas (REST):** listagem com paginação, filtros e ordenação; PATCH para edição inline; DELETE para exclusão — com checagem de `user_id`.
- **Importação CSV robusta:** tolerante a codificações (UTF-8/Latin-1), remoção de BOM, normalização de quebras de linha e detecção automática de delimitador; valida cabeçalhos e faz parsing seguro.
- **Exportação CSV:** conjuntos filtrados ou completos, servidos como download.
- **Dashboard com KPIs e tendências:** agregação mensal (custos totais, pagamentos vs. isentas, kWh, km derivados, consumo/100 km), além de estimativas de economia com base nas configurações de gasolina.
- **APIs para gráficos:** `/api/recharges` e `/api/recharges/monthly` retornam séries prontas para o front-end (Chart.js em `templates/partials/dashboard_charts.js`).
- **Filtros de moeda:** filtros Jinja `brl` e `usd` formatam valores para exibição.
- **Contato e logs:** mensagens registradas no SQLite e preparadas para SMTP via Flask-Mail, com credenciais em variáveis de ambiente.

---

##### Arquitetura e decisões
- **Escolha do framework:** Flask pela leveza, roteamento, renderização de templates e integração com Flask-Login, Babel, WTForms e CSRF.
- **Modelo de dados:** SQLite pela portabilidade. Tabelas incluem `users` (autenticação), `recharges` (registros), `settings` (preço da gasolina e média km/l) e `contact_logs` (mensagens).
- **i18n como padrão:** um `locale_selector` escolhe o idioma de forma consistente, enquanto rótulos/mensagens dos formulários são marcados para tradução.
- **Segurança:** CSRF habilitado; validações no servidor garantem entradas numéricas seguras; endpoints REST verificam propriedade antes de atualizar ou excluir.
- **Métricas derivadas:** km mensal derivado de min/max de odômetros (com fallbacks quando há apenas uma leitura); consumo por 100 km e custos por kWh/km computados no servidor.
- **Convenções de linguagem:** uso consistente de “recarga” para evitar confusão com termos como “top-up”.
- **Gráficos no front-end:** APIs entregam arrays prontos para Chart.js, mantendo o dashboard responsivo e desacoplado do banco.
- **Tolerância de importação:** o validador CSV sanitiza arquivos problemáticos (BOM, nulos, quebras de linha mistas) e tenta delimitadores comuns (vírgula, ponto e vírgula, tab).

---

##### Estrutura de arquivos
*(mesma estrutura apresentada acima, com comentários em português nos próprios nomes dos arquivos e comentários)*

---

##### Instalação e execução
1. **Criar e ativar o ambiente virtual**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # macOS/Linux
   .venv\Scripts\activate     # Windows
   ```
2. **Instalar dependências**
   ```bash
   pip install -r requirements.txt
   ```
3. **Variáveis de ambiente** (exemplos)
   ```bash
   export SECRET_KEY="uma_chave_segura"
   export MAIL_USERNAME="seu_email@gmail.com"
   export MAIL_PASSWORD="sua_app_password"
   ```
4. **Inicializar o banco** (se necessário)
   ```bash
   sqlite3 dados.db < schema.sql
   ```
5. **Executar a aplicação**
   ```bash
   python app.py
   # ou
   flask run
   ```

Para deploy em plataformas que usam **Procfile**, o comando costuma ser `web: gunicorn app:app`.

---

##### Fluxo de uso
- **Registro / Login** → acesso ao **Dashboard** com KPIs e gráficos.
- **Recarga individual** (`/recharge`) → formulário validado.
- **Importação em lote** (`/bulk_recharge`) → CSV robusto com feedback.
- **Configurações** (`/account`) → preço da gasolina e km/l médio para estimativa de economia.
- **Gerenciar** (`/manage_recharges`) → listar/filtrar/editar/excluir via endpoints REST.
- **Exportar CSV** (`/export_recharges`) → respeita os filtros correntes.
- **Contato** (`/contact`) → mensagem registrada em `contact_logs`.

---

##### Melhorias futuras
- Autorização por papel (admin/usuário) e auditoria de mudanças.
- Integrações com provedores de recarga públicos.
- Testes automatizados (unitários/integração) e CI/CD.
- Cache para agregações mensais e endpoints de gráficos.

---

