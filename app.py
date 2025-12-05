from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, g, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from flask_babel import Babel, gettext as _, lazy_gettext as _l
from flask_wtf import CSRFProtect, FlaskForm
import sqlite3
from wtforms import StringField, PasswordField, FloatField, DateField, TextAreaField, FileField, BooleanField, EmailField, SubmitField 
from wtforms.validators import DataRequired, Email, Length, NumberRange
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import csv
import io
import os
from collections import defaultdict
from datetime import datetime

# ----------------- CONFIGURAÇÕES INICIAIS DO FLASK -----------------
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "default_key")

# Adicione este bloco no app.py:
@app.context_processor
def inject_int_functions():
    """Injeta as funções de tradução _ e _l em todos os templates Jinja."""
    return dict(_=_, _l=_l)


# ----------------- Configuração do Gmail SMTP -----------------
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')  # seu email
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')  # app password
mail = Mail(app)


# ----------------- Configuração do Babel para internacionalização -----------------
app.config['LANGUAGES'] = ['pt_BR', 'en', 'es'] # Adicione os idiomas suportados
app.config['BABEL_DEFAULT_LOCALE'] = 'en' # Define o Inglês como padrão (fallback)
app.config['BABEL_TRANSLATION_DIRECTORIES'] = 'translations' # Diretório das traduções
#babel = Babel(app)

# Salva 'lang' da URL na sessão antes de cada request
@app.before_request
def set_language_from_query():
    lang = request.args.get('lang')
    if lang in app.config.get('LANGUAGES', []):
        session['lang'] = lang

# Função usada pelo Flask-Babel v4
def get_locale():
    # 1) Sessão (se o usuário trocou pelo link)
    lang = session.get('lang')
    if lang in app.config.get('LANGUAGES', []):
        return lang

    # 2) Se estiver logado e você guardar preferência no user (opcional)
    user = getattr(g, 'user', None)
    if user and getattr(user, 'locale', None) in app.config['LANGUAGES']:
        return user.locale

    # 3) Cabeçalho do navegador
    return request.accept_languages.best_match(app.config['LANGUAGES'])

# Mantém a inicialização do Babel com o selector
babel = Babel(app, locale_selector=get_locale)


# ----------------- Proteção CSRF -----------------
csrf = CSRFProtect(app)

# ----------------- Configuração do Flask-Login -----------------
login_manager = LoginManager(app)
login_manager.login_view = "index"


# ----------------- MODELO DE USUÁRIO -----------------
class User(UserMixin):
    def __init__(self, id, nome, email):
        self.id = id
        self.nome = nome
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect("dados.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, email FROM users WHERE id=?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return User(row[0], row[1], row[2])
    return None

# ----------------- FORMULÁRIOS -----------------
class LoginForm(FlaskForm):
    # Rótulos marcados para tradução
    email = StringField(_l("Email"), validators=[DataRequired(), Email()])
    senha = PasswordField(_l("Senha"), validators=[DataRequired()])
    submit = SubmitField(_l("Login")) # Adicionei um botão de submit para ser traduzido também

class RegisterForm(FlaskForm):
    # Rótulos marcados para tradução
    nome = StringField(_l("Nome"), validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField(_l("Email"), validators=[DataRequired(), Email()])
    senha = PasswordField(_l("Senha"), validators=[DataRequired(), Length(min=6)])
    submit = SubmitField(_l("Registrar")) # Adicionei um botão de submit

class RechargeForm(FlaskForm):
    # Rótulos marcados para tradução
    data = DateField(_l("Data"), validators=[DataRequired()])
    kwh = FloatField(_l("kWh"), validators=[DataRequired(), NumberRange(min=0.01)])
    custo = FloatField(_l("Custo"), validators=[DataRequired(), NumberRange(min=0.0)])
    isento = BooleanField(_l("Isento"))
    odometro = FloatField(_l("Odômetro"), validators=[DataRequired(), NumberRange(min=0.1)])
    local = StringField(_l("Local"))
    observacoes = TextAreaField(_l("Observações"))
    submit = SubmitField(_l("Salvar Recarga")) # Adicionei um botão de submit

class AccountForm(FlaskForm):
    # Rótulos marcados para tradução
    preco_gasolina = FloatField(_l("Preço da Gasolina"), validators=[DataRequired(), NumberRange(min=0.0)])
    consumo_km_l = FloatField(_l("Consumo Médio (km/l)"), validators=[DataRequired(), NumberRange(min=0.1)])
    submit = SubmitField(_l("Atualizar Configurações")) # Adicionei um botão de submit

class BulkRechargeForm(FlaskForm):
    # Rótulos marcados para tradução
    file = FileField(_l("Arquivo CSV"), validators=[DataRequired()])
    submit = SubmitField(_l("Importar")) # Adicionei um botão de submit

class ContactForm(FlaskForm):
    # Rótulos marcados para tradução
    nome = StringField(_l('Nome'), validators=[DataRequired()])
    email = StringField(_l('E-mail'), validators=[DataRequired(), Email()])
    mensagem = TextAreaField(_l('Mensagem'), validators=[DataRequired()])
    submit = SubmitField(_l('Enviar'))


# ----------------- FUNÇÃO AUXILIAR FORMATAR NÚMEROS (AUTO por idioma) -----------------
def brl(value, digitos=2, com_prefixo=True):
    """
    Formata números conforme o idioma atual:
      - pt_BR  -> padrão brasileiro (R$ 1.234,56)
      - outros -> padrão americano (US$ 1,234.56)
    Parâmetros:
      value: número a formatar (int/float/string numérica)
      digitos: casas decimais
      com_prefixo: se True, exibe 'R$ ' (pt_BR) ou '$ ' (demais); se False, só o número
    """
    try:
        v = float(value)
    except (ValueError, TypeError):
        # fallback visual quando não há valor numérico
        return "-"

    # Tenta obter o locale atual do Babel; cai para sessão/browser se necessário
    try:
        # get_locale foi definido no seu app e passado ao Babel como locale_selector
        lang = None
        # 1) sessão (se você troca via ?lang=)
        lang = session.get('lang')
        # 2) Babel (selector)
        if not lang:
            # Se get_locale existe, usa
            try:
                lang = str(get_locale())
            except Exception:
                lang = None
        # 3) cabeçalho do navegador (fallback)
        if not lang and request is not None:
            lang = request.accept_languages.best_match(app.config.get('LANGUAGES', []))
    except Exception:
        lang = None

    # Formata em string com separadores padrão US
    s_us = f"{v:,.{digitos}f}"  # ex.: 1234.56 -> "1,234.56"

    if lang == 'pt_BR':
        # Converte para padrão brasileiro: milhar '.' e decimal ','
        s_br = s_us.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {s_br}" if com_prefixo else s_br
    else:
        # Mantém padrão americano
        return f"$ {s_us}" if com_prefixo else s_us

# Atualiza/registrar filtro único 'brl' no Jinja (substitui os anteriores)
app.jinja_env.filters["brl"] = brl



# ----------------- FUNÇÃO AUXILIAR PARA CSV -----------------
def validate_csv_and_parse(file_storage):
    """
    Valida e processa um arquivo CSV enviado via upload.
    - Converte para UTF-8 puro (remove BOM, caracteres nulos)
    - Normaliza quebras de linha
    - Detecta delimitador automaticamente
    - Valida cabeçalhos e dados
    Retorna: (rows_validos, err_msgs)
    """

    err_msgs = []
    rows_validos = []

    # --- Sanitização do arquivo ---
    try:
        file_storage.stream.seek(0)
        raw = file_storage.read()
    except Exception as e:
        return [], [_(f"Erro ao ler arquivo: {e}")]

    # Decodificação com fallback
    try:
        text = raw.decode("utf-8-sig")  # remove BOM se existir
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="ignore")

    # Remove caracteres nulos (indicativo de UTF-16)
    text = text.replace("\x00", "")

    # Normaliza quebras de linha
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Cria stream seguro para csv
    stream = io.StringIO(text, newline='')

    # --- Detectar delimitador ---
    sample = text[:10000]
    delimiter = ','
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=[',', ';', '\t', '|'])
        delimiter = dialect.delimiter
    except Exception:
        # fallback simples
        first_line = text.splitlines()[0] if text.splitlines() else ""
        if ';' in first_line and ',' not in first_line:
            delimiter = ';'
        elif '\t' in first_line:
            delimiter = '\t'

    # --- Criar DictReader ---
    try:
        reader = csv.DictReader(stream, delimiter=delimiter)
    except Exception as e:
        return [], [_(f"Erro ao preparar leitor CSV: {e}")]

    # Validar cabeçalhos
    if not reader.fieldnames:
        return [], [_("Arquivo CSV sem cabeçalho.")]

    reader.fieldnames = [(h or "").strip().lower().replace('\ufeff', '') for h in reader.fieldnames]

    required_headers = ['data', 'kwh', 'custo', 'isento', 'odometro', 'local', 'observacoes']

    missing = [h for h in required_headers if h not in reader.fieldnames]
    if missing:
        msg = _(
            "Cabeçalhos inválidos. Esperado: %(expected)s. Ausentes: %(missing)s",
            expected=", ".join(required_headers),
            missing=", ".join(missing),
        )
        return [], [msg]


    # --- Processar linhas ---
    line_num = 1
    for row in reader:
        line_num += 1
        if all((row.get(h) is None or str(row.get(h)).strip() == "") for h in required_headers):
            continue

        try:
            data = (row.get('data') or "").strip()
            if not data:
                raise ValueError(_("Campo 'data' vazio."))

            kwh = float((row.get('kwh') or "").replace(',', '.'))
            custo = float((row.get('custo') or "").replace(',', '.'))
            odometro = float((row.get('odometro') or "").replace(',', '.'))

            local = (row.get('local') or "").strip()
            observacoes = (row.get('observacoes') or "").strip()

            isento_raw = (row.get('isento') or "").strip().lower()
            isento = isento_raw in ["true", "1", "sim", "yes", "y"]

            rows_validos.append({
                'data': data,
                'kwh': kwh,
                'custo': custo,
                'odometro': odometro,
                'isento': isento,
                'local': local,
                'observacoes': observacoes
            })

        except ValueError as ve:
            err_msgs.append(_(f"Linha {line_num}: {ve}. Conteúdo: {row}"))
        except Exception as e:
            err_msgs.append(_(f"Linha {line_num}: erro inesperado: {e}. Conteúdo: {row}"))

    if not rows_validos and not err_msgs:
        err_msgs.append(_("Nenhuma linha válida foi encontrada no CSV."))

    return rows_validos, err_msgs



# ----------------- ROTAS -----------------
@app.route("/")
def index():
    form = LoginForm()
    return render_template("index.html", form=form)

@app.route("/login", methods=["POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        senha = form.senha.data
        conn = sqlite3.connect("dados.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome, email, senha_hash FROM users WHERE email=?", (email,))
        row = cursor.fetchone()
        conn.close()
        if row and check_password_hash(row[3], senha):
            user = User(row[0], row[1], row[2])
            login_user(user)
            flash(_("Login realizado com sucesso!"), "success")
            return redirect(url_for("dashboard"))
        else:
            flash(_("Credenciais inválidas."), "danger")
            return redirect(url_for("index"))
    for field, errors in form.errors.items():
        for err in errors:
            flash(_(f"Erro em {field}: {err}"), "danger")
    return redirect(url_for("index"))

@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if request.method == "POST":
        if form.validate_on_submit():
            nome = form.nome.data
            email = form.email.data
            senha_hash = generate_password_hash(form.senha.data)
            conn = sqlite3.connect("dados.db")
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO users (nome, email, senha_hash) VALUES (?, ?, ?)", (nome, email, senha_hash))
                conn.commit()
                flash(_("Conta criada com sucesso! Faça login."), "success")
                return redirect(url_for("index"))
            except sqlite3.IntegrityError:
                flash(_("Email já cadastrado."), "danger")
            finally:
                conn.close()
        else:
            for field, errors in form.errors.items():
                for err in errors:
                    flash(_(f"Erro em {field}: {err}"), "danger")
    return render_template("register.html", form=form)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash(_("Você saiu da conta."), "info")
    return redirect(url_for("index"))

@app.route("/recharge", methods=["GET", "POST"])
@login_required
def recharge():
    form = RechargeForm()
    if request.method == "POST":
        if form.validate_on_submit():
            data = form.data.data.isoformat()
            kwh = form.kwh.data
            custo = form.custo.data
            odometro = form.odometro.data
            local = form.local.data
            observacoes = form.observacoes.data
            isento = 1 if form.isento.data else 0
            conn = sqlite3.connect("dados.db")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO recharges (user_id, data, kwh, custo, isento, odometro, local, observacoes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (int(current_user.id), data, kwh, custo, isento, odometro, local, observacoes))
            conn.commit()
            conn.close()
            flash(_("Recarga registrada com sucesso!"), "success")
            return redirect(url_for("dashboard"))
        else:
            for field, errors in form.errors.items():
                for err in errors:
                    flash(_(f"Erro em {field}: {err}"), "danger")
    return render_template("recharge.html", form=form)


@app.route("/bulk_recharge", methods=["GET", "POST"])
@login_required
def bulk_recharge():
    form = BulkRechargeForm()
    if request.method == "POST" and form.validate_on_submit():
        file = form.file.data

        # Usa a função robusta para sanitizar e validar CSV
        rows, errors = validate_csv_and_parse(file)

        if errors:
            for msg in errors:
                flash(msg, "danger")
            return redirect(url_for("bulk_recharge"))

        # Inserção no banco
        conn = sqlite3.connect("dados.db")
        cursor = conn.cursor()
        count_ok = 0
        for r in rows:
            try:
                cursor.execute("""
                    INSERT INTO recharges (user_id, data, kwh, custo, isento, odometro, local, observacoes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    int(current_user.id),
                    r['data'],
                    r['kwh'],
                    r['custo'],
                    r['isento'],
                    r['odometro'],
                    r['local'],
                    r['observacoes']
                ))
                count_ok += 1
            except Exception as e:
                flash(_(f"Falha ao inserir linha: {r}. Detalhes: {e}"), "warning")

        conn.commit()
        conn.close()

        flash(_(f"Importação concluída. {count_ok} recarga(s) adicionada(s)."), "success")
        return redirect(url_for("dashboard"))

    else:
        for field, errs in form.errors.items():
            for err in errs:
                flash(_(f"Erro em {field}: {err}"), "danger")

    return render_template("bulk_recharge.html", form=form)


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    form = AccountForm()
    conn = sqlite3.connect("dados.db")
    cursor = conn.cursor()
    if request.method == "POST":
        if form.validate_on_submit():
            preco_gasolina = form.preco_gasolina.data
            consumo_km_l = form.consumo_km_l.data
            cursor.execute("SELECT id FROM settings WHERE user_id=?", (int(current_user.id),))
            row = cursor.fetchone()
            if row:
                cursor.execute("UPDATE settings SET preco_gasolina=?, consumo_km_l=? WHERE user_id=?",
                               (preco_gasolina, consumo_km_l, int(current_user.id)))
            else:
                cursor.execute("INSERT INTO settings (user_id, preco_gasolina, consumo_km_l) VALUES (?, ?, ?)",
                               (int(current_user.id), preco_gasolina, consumo_km_l))
            conn.commit()
            conn.close()
            flash(_("Configurações atualizadas com sucesso!"), "success")
            return redirect(url_for("dashboard"))
        else:
            for field, errors in form.errors.items():
                for err in errors:
                    flash(_(f"Erro em {field}: {err}"), "danger")
    cursor.execute("SELECT preco_gasolina, consumo_km_l FROM settings WHERE user_id=?", (int(current_user.id),))
    config = cursor.fetchone()
    conn.close()
    if config:
        form.preco_gasolina.data = float(config[0])
        form.consumo_km_l.data = float(config[1])
    return render_template("account.html", form=form)


# ----------------- NOVA ROTA API PARA CHART.JS -----------------
@app.route("/api/recharges")
@login_required
def api_recharges():
    user_id = int(current_user.id)
    conn = sqlite3.connect("dados.db")
    cursor = conn.cursor()
    cursor.execute("SELECT data, kwh, custo, isento FROM recharges WHERE user_id=? ORDER BY data", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    labels = [r[0] for r in rows]
    kwh = [float(r[1]) for r in rows]
    custo = [float(r[2]) for r in rows]
    return jsonify({"labels": labels, "kwh": kwh, "custo": custo})



@app.route("/api/recharges/monthly")
@login_required
def api_recharges_monthly():
    user_id = int(current_user.id)

    # Buscar dados do usuário
    conn = sqlite3.connect("dados.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT data, kwh, custo, isento, odometro
        FROM recharges
        WHERE user_id=?
        ORDER BY date(data), id
    """, (user_id,))
    rows = cursor.fetchall()

    # Buscar configurações para cálculo de economia
    cursor.execute("SELECT preco_gasolina, consumo_km_l FROM settings WHERE user_id=?", (user_id,))
    config = cursor.fetchone()
    conn.close()

    preco_gasolina = float(config[0]) if config and config[0] is not None else None
    consumo_km_l = float(config[1]) if config and config[1] is not None else None
    tem_config = (preco_gasolina is not None) and (consumo_km_l is not None) and (consumo_km_l > 0)

    # Estrutura para agregação
    monthly = defaultdict(lambda: {
        "custo_total": 0.0,
        "custo_pagamento": 0.0,
        "kwh": 0.0,
        "odometros": []
    })

    # Processar linhas
    for data, kwh, custo, isento, odometro in rows:
        try:
            mes = datetime.fromisoformat(data).strftime("%Y-%m")  # 'YYYY-MM'
        except Exception:
            mes = str(data)[:7]

        monthly[mes]["custo_total"] += float(custo or 0)
        monthly[mes]["kwh"] += float(kwh or 0)
        if odometro is not None:
            monthly[mes]["odometros"].append(float(odometro))
        if not isento:
            monthly[mes]["custo_pagamento"] += float(custo or 0)

    # Meses em ordem cronológica
    meses_ord = sorted(monthly.keys())

    # Vetores para resposta
    labels = []
    custos_total = []
    custos_pagamento = []
    custos_percentual = []
    consumos = []
    kms = []
    economias_total = []
    economias_pagamento = []
    consumo_por_100km_list = []

    # Calcular economia, km e consumo/100km por mês
    for idx, mes in enumerate(meses_ord):
        data_mes = monthly[mes]
        labels.append(mes)

        # Custos
        ct = float(data_mes["custo_total"])
        cp = float(data_mes["custo_pagamento"])
        custos_total.append(round(ct, 2))
        custos_pagamento.append(round(cp, 2))
        custos_percentual.append(round((cp / ct * 100) if ct > 0 else 0.0, 2))

        # Consumo
        consumo_mes = round(float(data_mes["kwh"]), 2)
        consumos.append(consumo_mes)

        # Km rodados
        odos = data_mes["odometros"]
        if len(odos) >= 2:
            km_mes = max(odos) - min(odos)
        elif len(odos) == 1:
            if idx > 0:
                prev_odos = monthly[meses_ord[idx - 1]]["odometros"]
                prev_last = max(prev_odos) if prev_odos else 0.0
                km_mes = odos[0] - prev_last
            else:
                km_mes = 0.0
        else:
            km_mes = 0.0

        kms.append(round(km_mes, 2))

        # Consumo / 100Km
        if km_mes > 0:
            consumo_por_100km_list.append(round((consumo_mes / km_mes) * 100, 2))
        else:
            consumo_por_100km_list.append(0)

        # Economia (dependente de config)
        if tem_config:
            custo_gas_mes = (km_mes / consumo_km_l) * preco_gasolina
            economia_total_mes = custo_gas_mes - ct
            economia_pagamento_mes = custo_gas_mes - cp
        else:
            economia_total_mes = 0.0
            economia_pagamento_mes = 0.0

        economias_total.append(round(economia_total_mes, 2))
        economias_pagamento.append(round(economia_pagamento_mes, 2))

    # Resposta JSON
    return jsonify({
        "labels": labels,
        "custos": {
            "total": custos_total,
            "pagas": custos_pagamento,
            "percentual": custos_percentual
        },
        "consumo": consumos,
        "km": kms,
        "economia": {
            "total": economias_total,
            "pagas": economias_pagamento
        },
        "consumo_por_100km": consumo_por_100km_list
    })


# ----------------- ROTA DASHBOARD -----------------

@app.route("/dashboard")
@login_required
def dashboard():
    user_id = int(current_user.id)

    # Carregar dados
    conn = sqlite3.connect("dados.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, data, kwh, custo, isento, odometro, local, observacoes
        FROM recharges
        WHERE user_id=?
        ORDER BY date(data), id
    """, (user_id,))
    recargas = cursor.fetchall()

    cursor.execute("SELECT preco_gasolina, consumo_km_l FROM settings WHERE user_id=?", (user_id,))
    config = cursor.fetchone()
    conn.close()

    # KPIs principais
    kwhs = [float(r[2]) if r[2] else 0 for r in recargas]
    custos = [float(r[3]) if r[3] else 0 for r in recargas]
    isentos = [bool(r[4]) for r in recargas]
    odometros = [float(r[5]) if r[5] else 0 for r in recargas]

    total_recargas = len(recargas)
    recargas_isentas_qtd = sum(1 for i in isentos if i)
    recargas_pagas_qtd = total_recargas - recargas_isentas_qtd
    total_km = odometros[-1] - odometros[0] if len(odometros) >= 2 else (odometros[0] if odometros else 0)
    custo_total = sum(custos)
    custo_isentas = sum(c for c, i in zip(custos, isentos) if i)
    custo_pagas = sum(c for c, i in zip(custos, isentos) if not i)
    consumo_total_kwh = sum(kwhs)
    consumo_por_100km = (consumo_total_kwh / total_km * 100) if total_km > 0 else 0
    custo_medio_kwh = (custo_total / consumo_total_kwh) if consumo_total_kwh > 0 else 0
    custo_medio_km = (custo_total / total_km) if total_km > 0 else 0

    # Config gasolina
    tem_config = config and config[0] and config[1] and float(config[1]) > 0
    if tem_config:
        preco_gasolina = float(config[0])
        consumo_km_l = float(config[1])
        custo_gas_por_km = preco_gasolina / consumo_km_l
        custo_gas_total = (total_km / consumo_km_l) * preco_gasolina
        economia_total = custo_gas_total - custo_total
        economia_total_por_km = economia_total / total_km if total_km > 0 else 0
        economia_pagas = custo_gas_total - custo_pagas
        economia_pagas_por_km = economia_pagas / total_km if total_km > 0 else 0
    else:
        custo_gas_por_km = None
        custo_gas_total = None
        economia_total = None
        economia_total_por_km = None
        economia_pagas = None
        economia_pagas_por_km = None

    # KPIs dict
    kpis = {
        "recargas": total_recargas,
        "recargas_isentas_qtd": recargas_isentas_qtd,
        "recargas_pagas_qtd": recargas_pagas_qtd,
        "total_km": total_km,
        "consumo_total_kwh": consumo_total_kwh,
        "consumo_por_100km": consumo_por_100km,
        "custo_total": custo_total,
        "custo_isentas": custo_isentas,
        "custo_pagas": custo_pagas,
        "custo_medio_kwh": custo_medio_kwh,
        "custo_medio_km": custo_medio_km,
        "custo_gas_por_km": custo_gas_por_km,
        "custo_gas_total": custo_gas_total,
        "economia_total": economia_total,
        "economia_total_por_km": economia_total_por_km,
        "economia_pagas": economia_pagas,
        "economia_pagas_por_km": economia_pagas_por_km,
    }

    # ===== Cálculo das tendências =====
    from collections import defaultdict
    from datetime import datetime

    monthly = defaultdict(lambda: {"count_total": 0, "count_isentas": 0, "count_pagas": 0,
                                   "custo_total": 0, "custo_pagamento": 0, "kwh": 0, "odometros": []})

    for (_id, data, kwh, custo, isento, odometro, *_rest) in recargas:
        mes = datetime.fromisoformat(data).strftime("%Y-%m")
        monthly[mes]["count_total"] += 1
        monthly[mes]["custo_total"] += float(custo or 0)
        monthly[mes]["kwh"] += float(kwh or 0)
        if odometro: monthly[mes]["odometros"].append(float(odometro))
        if isento:
            monthly[mes]["count_isentas"] += 1
        else:
            monthly[mes]["count_pagas"] += 1
            monthly[mes]["custo_pagamento"] += float(custo or 0)

    meses = sorted(monthly.keys())
    curr_vals, prev_vals = {}, {}

    # Função auxiliar
    def percent_change(curr, prev):
        if prev is None or prev == 0: return None, 'flat'
        delta = curr - prev
        pct = (delta / prev) * 100
        return round(pct, 1), 'up' if delta > 0 else ('down' if delta < 0 else 'flat')

    # Último mês
    if meses:
        m = monthly[meses[-1]]
        km_mes = (max(m["odometros"]) - min(m["odometros"])) if len(m["odometros"]) >= 2 else (m["odometros"][0] if m["odometros"] else 0)
        curr_vals = {
            "recargas": m["count_total"],
            "recargas_isentas_qtd": m["count_isentas"],
            "recargas_pagas_qtd": m["count_pagas"],
            "total_km": km_mes,
            "consumo_total_kwh": m["kwh"],
            "consumo_por_100km": (m["kwh"] / km_mes * 100) if km_mes > 0 else 0,
            "custo_total": m["custo_total"],
            "custo_isentas": m["custo_total"] - m["custo_pagamento"],
            "custo_pagas": m["custo_pagamento"],
            "custo_medio_kwh": (m["custo_total"] / m["kwh"]) if m["kwh"] > 0 else 0,
            "custo_medio_km": (m["custo_total"] / km_mes) if km_mes > 0 else 0,
        }
        if tem_config:
            custo_gas_por_km_mes = preco_gasolina / consumo_km_l if consumo_km_l > 0 else 0
            custo_gas_total_mes = (km_mes / consumo_km_l) * preco_gasolina if consumo_km_l > 0 else 0
            curr_vals.update({
                "custo_gas_por_km": custo_gas_por_km_mes,
                "economia_total": custo_gas_total_mes - m["custo_total"],
                "economia_total_por_km": ((custo_gas_total_mes - m["custo_total"]) / km_mes) if km_mes > 0 else 0,
                "economia_pagas": custo_gas_total_mes - m["custo_pagamento"],
                "economia_pagas_por_km": ((custo_gas_total_mes - m["custo_pagamento"]) / km_mes) if km_mes > 0 else 0,
            })
        else:
            curr_vals.update({
                "custo_gas_por_km": None,
                "economia_total": None,
                "economia_total_por_km": None,
                "economia_pagas": None,
                "economia_pagas_por_km": None,
            })

    # Mês anterior
    if len(meses) > 1:
        m = monthly[meses[-2]]
        km_mes = (max(m["odometros"]) - min(m["odometros"])) if len(m["odometros"]) >= 2 else (m["odometros"][0] if m["odometros"] else 0)
        prev_vals = {
            "recargas": m["count_total"],
            "recargas_isentas_qtd": m["count_isentas"],
            "recargas_pagas_qtd": m["count_pagas"],
            "total_km": km_mes,
            "consumo_total_kwh": m["kwh"],
            "consumo_por_100km": (m["kwh"] / km_mes * 100) if km_mes > 0 else 0,
            "custo_total": m["custo_total"],
            "custo_isentas": m["custo_total"] - m["custo_pagamento"],
            "custo_pagas": m["custo_pagamento"],
            "custo_medio_kwh": (m["custo_total"] / m["kwh"]) if m["kwh"] > 0 else 0,
            "custo_medio_km": (m["custo_total"] / km_mes) if km_mes > 0 else 0,
        }
        if tem_config:
            custo_gas_por_km_mes = preco_gasolina / consumo_km_l if consumo_km_l > 0 else 0
            custo_gas_total_mes = (km_mes / consumo_km_l) * preco_gasolina if consumo_km_l > 0 else 0
            prev_vals.update({
                "custo_gas_por_km": custo_gas_por_km_mes,
                "economia_total": custo_gas_total_mes - m["custo_total"],
                "economia_total_por_km": ((custo_gas_total_mes - m["custo_total"]) / km_mes) if km_mes > 0 else 0,
                "economia_pagas": custo_gas_total_mes - m["custo_pagamento"],
                "economia_pagas_por_km": ((custo_gas_total_mes - m["custo_pagamento"]) / km_mes) if km_mes > 0 else 0,
            })
        else:
            prev_vals.update({
                "custo_gas_por_km": None,
                "economia_total": None,
                "economia_total_por_km": None,
                "economia_pagas": None,
                "economia_pagas_por_km": None,
            })

    # Monta tendências
    trends = {}
    for k in curr_vals.keys():
        pct, direction = percent_change(curr_vals.get(k), prev_vals.get(k))
        trends[k] = {"percent": pct, "direction": direction, "has_prev": prev_vals.get(k) is not None}

    return render_template("dashboard.html", recargas=recargas, kpis=kpis, trends=trends)


# ----------------- ROTA MANAGE RECHARGES -----------------
@app.route("/manage_recharges")
@login_required
def manage_recharges():
    return render_template("manage_recharges.html")


# ========== ENDPOINT 1: GET /api/manage_recharges ==========
@app.route('/api/manage_recharges')
@login_required
def api_manage_recharges():
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 20))
    sort_by = request.args.get('sort_by', 'data')
    sort_dir = request.args.get('sort_dir', 'asc')

    # Filtros
    local = request.args.get('local', '').strip()
    observacoes = request.args.get('observacoes', '').strip()
    isento = request.args.get('isento', 'all')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    # Validação sort_by
    valid_sort = ['data', 'kwh', 'custo', 'isento', 'odometro', 'local', 'observacoes']
    if sort_by not in valid_sort:
        sort_by = 'data'
    sort_dir = 'desc' if sort_dir == 'desc' else 'asc'

    user_id = int(current_user.id)
    conn = sqlite3.connect('dados.db')
    cursor = conn.cursor()

    # Monta cláusula WHERE
    where_clauses = ['user_id=?']
    params = [user_id]
    if local:
        where_clauses.append('LOWER(local) LIKE ?')
        params.append(f'%{local.lower()}%')
    if observacoes:
        where_clauses.append('LOWER(observacoes) LIKE ?')
        params.append(f'%{observacoes.lower()}%')
    if isento in ['true', 'false']:
        where_clauses.append('isento=?')
        params.append(1 if isento == 'true' else 0)
    if date_from:
        where_clauses.append('date(data) >= date(?)')
        params.append(date_from)
    if date_to:
        where_clauses.append('date(data) <= date(?)')
        params.append(date_to)

    where_sql = ' AND '.join(where_clauses)

    # Conta total
    cursor.execute(f'SELECT COUNT(*) FROM recharges WHERE {where_sql}', params)
    total = cursor.fetchone()[0]

    # Busca paginada
    offset = (page - 1) * page_size
    cursor.execute(f'''
        SELECT id, data, kwh, custo, isento, odometro, local, observacoes
        FROM recharges WHERE {where_sql}
        ORDER BY {sort_by} {sort_dir}
        LIMIT ? OFFSET ?
    ''', params + [page_size, offset])
    rows = cursor.fetchall()
    conn.close()

    items = []
    for r in rows:
        items.append({
            'id': r[0], 'data': r[1], 'kwh': r[2], 'custo': r[3],
            'isento': bool(r[4]), 'odometro': r[5], 'local': r[6], 'observacoes': r[7]
        })

    return jsonify({
        'items': items,
        'page': page,
        'page_size': page_size,
        'total': total,
        'has_prev': page > 1,
        'has_next': page * page_size < total
    })

# ========== ENDPOINT 2: PATCH /api/manage_recharges/<id> ==========
@app.route('/api/manage_recharges/<int:recarga_id>', methods=['PATCH'])
@login_required
@csrf.exempt
def api_update_recharge(recarga_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'invalid_payload'}), 400

    # Validação básica
    required_fields = ['data', 'kwh', 'custo', 'odometro']
    errors = {}
    for f in required_fields:
        if f not in data or str(data[f]).strip() == '':
            errors[f] = _('Campo obrigatório')
    if errors:
        return jsonify({'error': 'validation_failed', 'fields': errors}), 400

    try:
        kwh = float(data['kwh'])
        custo = float(data['custo'])
        odometro = float(data['odometro'])
        if kwh <= 0: errors['kwh'] = _('Deve ser > 0')
        if custo < 0: errors['custo'] = _('Não pode ser negativo')
        if odometro <= 0: errors['odometro'] = _('Deve ser > 0')
    except ValueError:
        return jsonify({'error': 'invalid_number_format'}), 400

    if errors:
        return jsonify({'error': 'validation_failed', 'fields': errors}), 400

    # Atualiza no banco
    conn = sqlite3.connect('dados.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM recharges WHERE id=?', (recarga_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'not_found'}), 404
    if row[0] != int(current_user.id):
        conn.close()
        return jsonify({'error': 'forbidden'}), 403

    cursor.execute('''
        UPDATE recharges SET data=?, kwh=?, custo=?, isento=?, odometro=?, local=?, observacoes=? WHERE id=?
    ''', (
        data['data'], kwh, custo, 1 if data.get('isento') else 0,
        odometro, data.get('local', ''), data.get('observacoes', ''), recarga_id
    ))
    conn.commit()

    cursor.execute('SELECT id, data, kwh, custo, isento, odometro, local, observacoes FROM recharges WHERE id=?', (recarga_id,))
    r = cursor.fetchone()
    conn.close()

    return jsonify({'updated': True, 'item': {
        'id': r[0], 'data': r[1], 'kwh': r[2], 'custo': r[3],
        'isento': bool(r[4]), 'odometro': r[5], 'local': r[6], 'observacoes': r[7]
    }})

# ========== ENDPOINT 3: DELETE /api/manage_recharges/<id> ==========
@app.route('/api/manage_recharges/<int:recarga_id>', methods=['DELETE'])
@login_required
@csrf.exempt
def api_delete_recharge(recarga_id):
    conn = sqlite3.connect('dados.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM recharges WHERE id=?', (recarga_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'not_found'}), 404
    if row[0] != int(current_user.id):
        conn.close()
        return jsonify({'error': 'forbidden'}), 403

    cursor.execute('DELETE FROM recharges WHERE id=?', (recarga_id,))
    conn.commit()
    conn.close()
    return jsonify({'deleted': True})



# ----------------- ROTA EXPORTAR RECHARGES CSV -----------------
@app.route('/export_recharges')
@login_required
def export_recharges():
    # Captura filtros
    local = request.args.get('local', '').strip()
    observacoes = request.args.get('observacoes', '').strip()
    isento = request.args.get('isento', 'all')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    user_id = int(current_user.id)
    conn = sqlite3.connect('dados.db')
    cursor = conn.cursor()

    # WHERE
    where_clauses = ['user_id=?']
    params = [user_id]
    if local:
        where_clauses.append('LOWER(local) LIKE ?')
        params.append(f'%{local.lower()}%')
    if observacoes:
        where_clauses.append('LOWER(observacoes) LIKE ?')
        params.append(f'%{observacoes.lower()}%')
    if isento in ['true', 'false']:
        where_clauses.append('isento=?')
        params.append(1 if isento == 'true' else 0)
    if date_from:
        where_clauses.append('date(data) >= date(?)')  # ✅ sem entidades HTML
        params.append(date_from)
    if date_to:
        where_clauses.append('date(data) <= date(?)')  # ✅ sem entidades HTML
        params.append(date_to)

    where_sql = ' AND '.join(where_clauses)

    cursor.execute(f'''
        SELECT data, kwh, custo, isento, odometro, local, observacoes
        FROM recharges
        WHERE {where_sql}
        ORDER BY date(data), id
    ''', params)
    rows = cursor.fetchall()
    conn.close()

    # CSV em memória (newline='' evita linhas em branco em alguns ambientes)
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['Data', 'kWh', 'Custo', 'Isento', 'Odômetro', 'Local', 'Observações'])
    for data, kwh, custo, isento, odometro, local_val, obs in rows:
        writer.writerow([
            data,
            kwh,
            custo,
            True if isento else False,
            odometro,
            local_val or '',
            obs or ''
        ])

    # Decide o nome do arquivo conforme filtros
    filtros_aplicados = any([
        bool(local),
        bool(observacoes),
        isento in ['true', 'false'],
        bool(date_from),
        bool(date_to)
    ])
    filename = (
        'recharge_export_filtered.csv'
        if filtros_aplicados
        else 'recharge_export_complete.csv'
    )

    # Retorna como arquivo para download
    return Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )



# ----------------- ENVIAR MENSAGEM AO CRIADOR -----------------
@app.route('/contact', methods=['GET', 'POST'])
@login_required
def contact():
    # Inicializa o formulário WTForms
    form = ContactForm()
    
    # Valida o formulário quando enviado via POST
    if form.validate_on_submit():
        # Captura os dados validados do formulário WTForms
        nome = form.nome.data
        email = form.email.data
        mensagem = form.mensagem.data # <-- A variável 'mensagem' agora está definida aqui

        # --- Atribuir a mensagem a uma variável 'msg' ---
        msg = Message(
            subject=f'EVChargeLog.com - {nome}',
            sender=os.getenv('MAIL_USERNAME'),  # usa seu e-mail para evitar rejeição
            recipients=[os.getenv('MAIL_USERNAME')],
            body=f'Nome: {nome}\nEmail: {email}\n\nMensagem:\n{mensagem}'
        )

        status = 'sucesso'

        '''
        try:
            # Envia a mensagem
            mail.send(msg)
            flash('Mensagem enviada com sucesso!')
        except Exception as e:
            status = f'erro: {str(e)}'
            flash('Erro ao enviar mensagem. Tente novamente mais tarde.')
        '''
        
        # Log no SQLite
        conn = sqlite3.connect('dados.db')
        cursor = conn.cursor()
        
        # --- Usar isoformat() para o tipo TIMESTAMP no SQLITE ---
        data_envio = datetime.now().isoformat() 

        cursor.execute('''
            INSERT INTO contact_logs (nome, email, mensagem, data_envio, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (nome, email, mensagem, data_envio, status))
        
        conn.commit()
        conn.close()

        # Simula envio bem-sucedido
        flash(_('Mensagem enviada com sucesso!'))

        # Redireciona para evitar reenvio do formulário ao atualizar a página
        return redirect(url_for('contact'))

    # Se o método for GET ou a validação falhar, renderiza o template com o formulário
    return render_template('contact.html', form=form)



# ----------------- RODA APLICACAO -----------------
if __name__ == "__main__":
    #app.run(debug=True)
    app.run(host="0.0.0.0", port=5000)