from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from flask_wtf import CSRFProtect, FlaskForm
from wtforms import StringField, PasswordField, FloatField, DateField, TextAreaField, FileField, BooleanField
from wtforms.validators import DataRequired, Email, Length, NumberRange
from werkzeug.utils import secure_filename
import csv
import io
import os
from collections import defaultdict
from datetime import datetime


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "default_key")
csrf = CSRFProtect(app)

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
    email = StringField("Email", validators=[DataRequired(), Email()])
    senha = PasswordField("Senha", validators=[DataRequired()])

class RegisterForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    senha = PasswordField("Senha", validators=[DataRequired(), Length(min=6)])

class RechargeForm(FlaskForm):
    data = DateField("Data", validators=[DataRequired()])
    kwh = FloatField("kWh", validators=[DataRequired(), NumberRange(min=0.01)])
    custo = FloatField("Custo", validators=[DataRequired(), NumberRange(min=0.0)])
    isento = BooleanField("Isento")  # ✅ Campo adicionado
    odometro = FloatField("Odômetro", validators=[DataRequired(), NumberRange(min=0.1)])
    local = StringField("Local")
    observacoes = TextAreaField("Observações")

class AccountForm(FlaskForm):
    preco_gasolina = FloatField("Preço da Gasolina", validators=[DataRequired(), NumberRange(min=0.0)])
    consumo_km_l = FloatField("Consumo Médio (km/l)", validators=[DataRequired(), NumberRange(min=0.1)])

class BulkRechargeForm(FlaskForm):
    file = FileField("Arquivo CSV", validators=[DataRequired()])


# ----------------- FUNÇÃO AUXILIAR FORMATAR NÚMEROS -----------------
def usd(value, digitos=2):
    """Format value as USD."""
    try:
        v = float(value)
        # separador de milhar (.) e decimal (,)
        s = f"{v:,.{digitos}f}"
        return f"$ {s}" if com_prefixo else s
    except (ValueError, TypeError):
        # fallback visual quando não há valor numérico
        return "-"

def brl(value, digitos=2, com_prefixo=True):
    """Formata números no padrão brasileiro; opcionalmente prefixa com R$."""
    try:
        v = float(value)
        # separador de milhar (.) e decimal (,)
        s = f"{v:,.{digitos}f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {s}" if com_prefixo else s
    except (ValueError, TypeError):
        # fallback visual quando não há valor numérico
        return "-"

app.jinja_env.filters["usd"] = usd
app.jinja_env.filters["brl"] = brl


# ----------------- FUNÇÃO AUXILIAR PARA CSV -----------------
def validate_csv_and_parse(file_storage):
    err_msgs = []
    rows_validos = []
    filename = secure_filename(file_storage.filename or "")
    if not filename.lower().endswith(".csv"):
        err_msgs.append("Formato inválido. Envie um arquivo .csv.")
        return [], err_msgs
    try:
        raw = file_storage.read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        stream = io.StringIO(text)
        reader = csv.DictReader(stream)
    except Exception as e:
        err_msgs.append(f"Erro ao ler o arquivo: {e}")
        return [], err_msgs
    
    reader = csv.DictReader(stream)
    if not reader.fieldnames:
        err_msgs.append("Arquivo CSV sem cabeçalho.")
        return [], err_msgs

    # Remove BOM e espaços
    reader.fieldnames = [h.strip().lower().replace('\ufeff', '') for h in reader.fieldnames]

    required_headers = ['data', 'kwh', 'custo', 'isento', 'odometro', 'local', 'observacoes']
    if not reader.fieldnames:
        err_msgs.append("Arquivo CSV sem cabeçalho.")
        return [], err_msgs
    missing = [h for h in required_headers if h not in reader.fieldnames]
    if missing:
        err_msgs.append("Cabeçalhos inválidos. Esperado: " + ", ".join(required_headers))
        err_msgs.append("Ausentes: " + ", ".join(missing))
        return [], err_msgs

    line_num = 1
    for row in reader:
        line_num += 1
        if all((row.get(h) is None or str(row.get(h)).strip() == "") for h in required_headers):
            continue
        try:
            data = (row.get('data') or "").strip()
            kwh = float(row.get('kwh'))
            custo = float(row.get('custo'))
            odometro = float(row.get('odometro'))
            local = (row.get('local') or "").strip()
            observacoes = (row.get('observacoes') or "").strip()

            isento_raw = (row.get('isento') or "").strip().lower()
            # Conversão para booleano
            isento = isento_raw in ["true", "1", "sim", "yes"]

            if not data:
                raise ValueError("Campo 'data' vazio.")
            if kwh <= 0:
                raise ValueError("kWh deve ser > 0.")
            if custo < 0:
                raise ValueError("Custo deve ser >= 0.")
            if odometro < 0:
                raise ValueError("Odômetro deve ser >= 0.")
            rows_validos.append({
                'data': data,
                'kwh': kwh,
                'custo': custo,
                'odometro': odometro,
                'isento': isento,  # ✅ Campo adicionado
                'local': local,
                'observacoes': observacoes
            })
        except Exception as e:
            err_msgs.append(f"Linha {line_num}: {e}. Conteúdo: {row}")
    if not rows_validos and not err_msgs:
        err_msgs.append("Nenhuma linha válida foi encontrada no CSV.")
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
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Credenciais inválidas.", "danger")
            return redirect(url_for("index"))
    for field, errors in form.errors.items():
        for err in errors:
            flash(f"Erro em {field}: {err}", "danger")
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
                flash("Conta criada com sucesso! Faça login.", "success")
                return redirect(url_for("index"))
            except sqlite3.IntegrityError:
                flash("Email já cadastrado.", "danger")
            finally:
                conn.close()
        else:
            for field, errors in form.errors.items():
                for err in errors:
                    flash(f"Erro em {field}: {err}", "danger")
    return render_template("register.html", form=form)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Você saiu da conta.", "info")
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
            conn = sqlite3.connect("dados.db")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO recharges (user_id, data, kwh, custo, isento, odometro, local, observacoes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (int(current_user.id), data, kwh, custo, isento, odometro, local, observacoes))
            conn.commit()
            conn.close()
            flash("Recarga registrada com sucesso!", "success")
            return redirect(url_for("dashboard"))
        else:
            for field, errors in form.errors.items():
                for err in errors:
                    flash(f"Erro em {field}: {err}", "danger")
    return render_template("recharge.html", form=form)

@app.route("/bulk_recharge", methods=["GET", "POST"])
@login_required
def bulk_recharge():
    form = BulkRechargeForm()
    if request.method == "POST" and form.validate_on_submit():
        file = form.file.data
        rows, errors = validate_csv_and_parse(file)
        if errors:
            for msg in errors:
                flash(msg, "danger")
            return redirect(url_for("bulk_recharge"))
        conn = sqlite3.connect("dados.db")
        cursor = conn.cursor()
        count_ok = 0
        for r in rows:
            try:
                cursor.execute("""
                    INSERT INTO recharges (user_id, data, kwh, custo, isento, odometro, local, observacoes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (int(current_user.id), r['data'], r['kwh'], r['custo'], r['isento'], r['odometro'], r['local'], r['observacoes']))
                count_ok += 1
            except Exception as e:
                flash(f"Falha ao inserir linha: {r}. Detalhes: {e}", "warning")
        conn.commit()
        conn.close()
        flash(f"Importação concluída. {count_ok} recarga(s) adicionada(s).", "success")
        return redirect(url_for("dashboard"))
    else:
        for field, errs in form.errors.items():
            for err in errs:
                flash(f"Erro em {field}: {err}", "danger")
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
            flash("Configurações atualizadas com sucesso!", "success")
            return redirect(url_for("dashboard"))
        else:
            for field, errors in form.errors.items():
                for err in errors:
                    flash(f"Erro em {field}: {err}", "danger")
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
            # fallback simples: pegar 'YYYY-MM' do início da string
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

    # Calcular economia e km por mês
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
        consumos.append(round(float(data_mes["kwh"]), 2))

        # Km rodados
        odos = data_mes["odometros"]
        if len(odos) >= 2:
            # Dentro do mês: diferença entre maior e menor
            km_mes = max(odos) - min(odos)
        elif len(odos) == 1:
            # Apenas um registro no mês: usa diferença vs último odômetro do mês anterior
            if idx > 0:
                prev_odos = monthly[meses_ord[idx - 1]]["odometros"]
                prev_last = max(prev_odos) if prev_odos else 0.0
                km_mes = odos[0] - prev_last
            else:
                km_mes = 0.0
        else:
            km_mes = 0.0

        kms.append(round(km_mes, 2))

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
        }
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


if __name__ == "__main__":
    #app.run(debug=True)
    app.run(host="0.0.0.0", port=5000)
