
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from flask_wtf import CSRFProtect, FlaskForm
from wtforms import StringField, PasswordField, FloatField, DateField, TextAreaField, FileField
from wtforms.validators import DataRequired, Email, Length, NumberRange
from werkzeug.utils import secure_filename
import csv
import io
import os

app = Flask(__name__)
#app.secret_key = "supersecretkey"  # TODO: usar variável de ambiente em produção

# Usa variável de ambiente em produção, com fallback para desenvolvimento
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

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
    odometro = FloatField("Odômetro", validators=[DataRequired(), NumberRange(min=0.1)])
    local = StringField("Local")
    observacoes = TextAreaField("Observações")

class AccountForm(FlaskForm):
    preco_gasolina = FloatField("Preço da Gasolina", validators=[DataRequired(), NumberRange(min=0.0)])
    consumo_km_l = FloatField("Consumo Médio (km/l)", validators=[DataRequired(), NumberRange(min=0.1)])

class BulkRechargeForm(FlaskForm):
    file = FileField("Arquivo CSV", validators=[DataRequired()])

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

    required_headers = ['data', 'kwh', 'custo', 'odometro', 'local', 'observacoes']
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
            if not data:
                raise ValueError("Campo 'data' vazio.")
            if kwh <= 0:
                raise ValueError("kWh deve ser > 0.")
            if custo < 0:
                raise ValueError("Custo deve ser >= 0.")
            if odometro <= 0:
                raise ValueError("Odômetro deve ser > 0.")
            rows_validos.append({
                'data': data,
                'kwh': kwh,
                'custo': custo,
                'odometro': odometro,
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
                INSERT INTO recharges (user_id, data, kwh, custo, odometro, local, observacoes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (int(current_user.id), data, kwh, custo, odometro, local, observacoes))
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
                    INSERT INTO recharges (user_id, data, kwh, custo, odometro, local, observacoes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (int(current_user.id), r['data'], r['kwh'], r['custo'], r['odometro'], r['local'], r['observacoes']))
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
    cursor.execute("SELECT data, kwh, custo FROM recharges WHERE user_id=? ORDER BY data", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    labels = [r[0] for r in rows]
    kwh = [float(r[1]) for r in rows]
    custo = [float(r[2]) for r in rows]
    return jsonify({"labels": labels, "kwh": kwh, "custo": custo})

# ----------------- ROTA DASHBOARD -----------------
@app.route("/dashboard")
@login_required
def dashboard():
    user_id = int(current_user.id)
    conn = sqlite3.connect("dados.db")
    cursor = conn.cursor()
    cursor.execute("SELECT data, kwh, custo, odometro, local, observacoes FROM recharges WHERE user_id=? ORDER BY data", (user_id,))
    recargas = cursor.fetchall()
    cursor.execute("SELECT preco_gasolina, consumo_km_l FROM settings WHERE user_id=?", (user_id,))
    config = cursor.fetchone()
    conn.close()

    datas = [r[0] for r in recargas]
    kwhs = [float(r[1]) for r in recargas]
    custos = [float(r[2]) for r in recargas]
    odometros = [float(r[3]) for r in recargas]

    km_por_intervalo = []
    economia_por_intervalo = []
    if len(recargas) >= 2:
        preco_gasolina = float(config[0]) if config else 0.0
        consumo_km_l = float(config[1]) if config else 1.0
        for i in range(1, len(recargas)):
            delta_km = odometros[i] - odometros[i - 1]
            if delta_km < 0:
                delta_km = 0
            km_por_intervalo.append(delta_km)
            custo_eletric = custos[i - 1]
            custo_gas = (delta_km / consumo_km_l) * preco_gasolina if consumo_km_l > 0 else 0.0
            economia_por_intervalo.append(custo_gas - custo_eletric)

    total_recargas = len(recargas)
    total_kwh = sum(kwhs) if recargas else 0.0
    total_custo = sum(custos) if recargas else 0.0
    total_km = sum(km_por_intervalo) if km_por_intervalo else 0.0
    custo_medio_kwh = (total_custo / total_kwh) if total_kwh > 0 else 0.0
    custo_medio_km = (total_custo / total_km) if total_km > 0 else 0.0
    economia_total = sum(economia_por_intervalo) if economia_por_intervalo else 0.0
    economia_media_km = (economia_total / total_km) if total_km > 0 else 0.0

    kpis = {
        'total_recargas': total_recargas,
        'total_kwh': total_kwh,
        'total_custo': total_custo,
        'total_km': total_km,
        'custo_medio_kwh': custo_medio_kwh,
        'custo_medio_km': custo_medio_km,
        'economia_total': economia_total,
        'economia_media_km': economia_media_km,
    }

    return render_template("dashboard.html", recargas=recargas, kpis=kpis)

if __name__ == "__main__":
    #app.run(debug=True)
    app.run(host="0.0.0.0", port=5000)

