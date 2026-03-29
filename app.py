from flask import Flask, render_template, request, redirect, url_for, session, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
from collections import defaultdict
from db import get_db, close_db
import os
import base64

from openai import OpenAI
client = OpenAI(api_key="A_TUA_API_KEY_AQUI")

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import cm
from io import BytesIO

import matplotlib.pyplot as plt


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_inseguro")


# ============================================================
# LOGIN REQUIRED
# ============================================================
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


# ============================================================
# IA — EXTRAÇÃO DE DADOS DA FATURA (CORRIGIDA)
# ============================================================
def extrair_dados_fatura(caminho):
    # Converter imagem para base64
    with open(caminho, "rb") as img:
        imagem_base64 = base64.b64encode(img.read()).decode("utf-8")

    resposta = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Extrai dados de uma fatura. Devolve JSON com descricao, valor, data e categoria."
            },
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Extrai os dados desta fatura."},
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{imagem_base64}"
                    }
                ]
            }
        ]
    )

    texto = resposta.choices[0].message["content"]

    import json
    try:
        dados = json.loads(texto)
    except:
        dados = {"descricao": "", "valor": 0, "data": "", "categoria": ""}

    return dados


# ============================================================
# CATEGORIZAÇÃO AUTOMÁTICA
# ============================================================
def categorizar_despesa(descricao):
    descricao = descricao.lower()

    categorias = {
        "despesas_variaveis": ["agua", "luz", "eletricidade", "electricidade", "gás", "gas"],
        "despesas_fixas": ["renda", "aluguer", "emprestimo", "tv", "telefone", "internet"],
        "saude": ["consulta", "médico", "medico", "ato", "exame"],
        "desporto": ["tenis", "raquete", "prancha", "surf", "ginásio", "ginasio"],
        "educacao": ["escola", "propina", "curso", "formação", "formacao"],
        "refeicoes": ["restaurante", "snack", "lanche", "café", "cafe", "almoço", "jantar"],
        "diversao": ["cinema", "jogo", "bar", "evento", "festa"]
    }

    for categoria, palavras in categorias.items():
        if any(p in descricao for p in palavras):
            return categoria

    return "outras"


# ============================================================
# REGISTO
# ============================================================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, password)
            )
            db.commit()
            return redirect(url_for("login"))
        except:
            return "Utilizador já existe."

    return render_template("register.html")


# ============================================================
# LOGIN
# ============================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))
        else:
            return "Credenciais inválidas."

    return render_template("login.html")


# ============================================================
# LANDING PAGE
# ============================================================
@app.route("/landing")
def landing():
    return render_template("landing.html")


@app.route("/")
def home():
    return redirect(url_for("landing"))
# ============================================================
# DASHBOARD
# ============================================================
@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    user_id = session["user_id"]
    db = get_db()

    if request.method == "POST":
        tipo = request.form.get("tipo_form")

        # -----------------------------
        # DESPESA (com IA)
        # -----------------------------
        if tipo == "despesa":
            descricao = request.form.get("descricao")
            valor = request.form.get("valor")
            data = request.form.get("data")

            fatura = request.files.get("fatura")
            caminho_fatura = None

            if fatura and fatura.filename:
                os.makedirs("static/faturas", exist_ok=True)
                caminho_fatura = f"static/faturas/{user_id}_{datetime.now().timestamp()}.jpg"
                fatura.save(caminho_fatura)

                dados = extrair_dados_fatura(caminho_fatura)

                if not descricao:
                    descricao = dados.get("descricao", "")
                if not valor:
                    valor = dados.get("valor", 0)
                if not data:
                    data = dados.get("data", datetime.now().strftime("%Y-%m-%d"))

            valor = float(valor)

            db.execute(
                "INSERT INTO despesas (user_id, descricao, valor, data) VALUES (?, ?, ?, ?)",
                (user_id, descricao, valor, data)
            )
            db.commit()

            return redirect(url_for("dashboard"))

        # -----------------------------
        # INVESTIMENTO
        # -----------------------------
        elif tipo == "investimento":
            valor = float(request.form["investimento"])
            data = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db.execute(
                "INSERT INTO aportes (user_id, valor, data) VALUES (?, ?, ?)",
                (user_id, valor, data)
            )
            db.commit()

            return redirect(url_for("dashboard"))

    despesas = db.execute(
        "SELECT * FROM despesas WHERE user_id = ?", (user_id,)
    ).fetchall()

    investimentos = db.execute(
        "SELECT * FROM aportes WHERE user_id = ?", (user_id,)
    ).fetchall()

    invest = sum(a["valor"] for a in investimentos)
    total_despesas = sum(d["valor"] for d in despesas)
    saldo = invest - total_despesas

    despesas_por_categoria = defaultdict(float)
    for d in despesas:
        despesas_por_categoria[d["descricao"]] += d["valor"]

    categorias = list(despesas_por_categoria.keys())
    valores_categoria = list(despesas_por_categoria.values())

    por_mes = defaultdict(float)
    for d in despesas:
        data_str = d["data"]
        if not data_str:
            continue

        dt = None
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(data_str, fmt)
                break
            except ValueError:
                continue
        if not dt:
            continue

        chave = dt.strftime("%Y-%m")
        por_mes[chave] += d["valor"]

    aporte_por_mes = defaultdict(float)
    for a in investimentos:
        data_str = a["data"]
        if not data_str:
            continue

        dt = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(data_str, fmt)
                break
            except ValueError:
                continue
        if not dt:
            continue

        chave = dt.strftime("%Y-%m")
        aporte_por_mes[chave] += a["valor"]

    todos_os_meses = sorted(
        set(list(por_mes.keys()) + list(aporte_por_mes.keys())),
        key=lambda x: datetime.strptime(x, "%Y-%m")
    )

    despesas_mes = [por_mes.get(m, 0) for m in todos_os_meses]
    aportes_mes = [aporte_por_mes.get(m, 0) for m in todos_os_meses]
    saldo_mes = [aporte_por_mes.get(m, 0) - por_mes.get(m, 0) for m in todos_os_meses]

    return render_template(
        "index.html",
        despesas=despesas,
        aporte_mensal=invest,
        total_despesas=total_despesas,
        saldo_planeado=saldo,

        categorias=categorias,
        valores_categoria=valores_categoria,

        labels_combinado=todos_os_meses,
        despesas_mes=despesas_mes,
        aportes_mes=aportes_mes,
        saldo_mes=saldo_mes
    )


# ============================================================
# FECHAR MÊS
# ============================================================
@app.route("/fechar_mes")
@login_required
def fechar_mes():
    user_id = session["user_id"]
    db = get_db()

    mes_atual = datetime.now().strftime("%Y-%m")

    despesas = db.execute(
        "SELECT descricao, valor, data FROM despesas WHERE user_id = ?",
        (user_id,)
    ).fetchall()

    for d in despesas:
        db.execute("""
            INSERT INTO historico_despesas (user_id, descricao, valor, data, mes_referente)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, d["descricao"], d["valor"], d["data"], mes_atual))

    aportes = db.execute(
        "SELECT valor, data FROM aportes WHERE user_id = ?",
        (user_id,)
    ).fetchall()

    for a in aportes:
        db.execute("""
            INSERT INTO historico_aportes (user_id, valor, data, mes_referente)
            VALUES (?, ?, ?, ?)
        """, (user_id, a["valor"], a["data"], mes_atual))

    db.execute("DELETE FROM despesas WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM aportes WHERE user_id = ?", (user_id,))
    db.commit()

    return redirect(url_for("historico"))


# ============================================================
# HISTÓRICO
# ============================================================
@app.route("/historico")
@login_required
def historico():
    user_id = session["user_id"]
    db = get_db()

    meses = db.execute("""
        SELECT DISTINCT mes_referente 
        FROM (
            SELECT mes_referente FROM historico_despesas WHERE user_id = ?
            UNION
            SELECT mes_referente FROM historico_aportes WHERE user_id = ?
        )
        ORDER BY mes_referente DESC
    """, (user_id, user_id)).fetchall()

    historico_por_mes = {}

    for m in meses:
        mes = m["mes_referente"]

        despesas = db.execute("""
            SELECT descricao, valor, data
            FROM historico_despesas
            WHERE user_id = ? AND mes_referente = ?
        """, (user_id, mes)).fetchall()

        aportes = db.execute("""
            SELECT valor, data
            FROM historico_aportes
            WHERE user_id = ? AND mes_referente = ?
        """, (user_id, mes)).fetchall()

        total_despesas = sum(d["valor"] for d in despesas)
        total_aportes = sum(a["valor"] for a in aportes)
        saldo = total_aportes - total_despesas

        historico_por_mes[mes] = {
            "despesas": despesas,
            "aportes": aportes,
            "total_despesas": total_despesas,
            "total_aportes": total_aportes,
            "saldo": saldo
        }

    return render_template("historico.html", historico=historico_por_mes)
# ============================================================
# PDF PREMIUM — CAPA + SUMÁRIO + TABELAS
# ============================================================
@app.route("/exportar_pdf")
@login_required
def exportar_pdf():
    user_id = session["user_id"]
    db = get_db()

    # Histórico de despesas
    historico = db.execute("""
        SELECT descricao, valor, data, mes_referente
        FROM historico_despesas
        WHERE user_id = ?
    """, (user_id,)).fetchall()

    # Histórico de aportes
    historico_aportes = db.execute("""
        SELECT valor, data, mes_referente
        FROM historico_aportes
        WHERE user_id = ?
    """, (user_id,)).fetchall()

    # Organizar despesas por categoria
    categorias = {
        "Despesas Variáveis": [],
        "Despesas Fixas": [],
        "Saúde": [],
        "Desporto": [],
        "Educação": [],
        "Refeições / Snacks": [],
        "Diversão": [],
        "Outras": []
    }

    for item in historico:
        cat = categorizar_despesa(item["descricao"])
        nome_cat = {
            "despesas_variaveis": "Despesas Variáveis",
            "despesas_fixas": "Despesas Fixas",
            "saude": "Saúde",
            "desporto": "Desporto",
            "educacao": "Educação",
            "refeicoes": "Refeições / Snacks",
            "diversao": "Diversão",
            "outras": "Outras"
        }.get(cat, "Outras")

        categorias[nome_cat].append(item)

    # Criar gráfico em tarte das despesas por categoria
    labels = []
    sizes = []
    for nome_cat, lista in categorias.items():
        total_cat = sum(i["valor"] for i in lista)
        if total_cat > 0:
            labels.append(nome_cat)
            sizes.append(total_cat)

    grafico_path = "static/grafico_tarte.png"
    if sizes:
        plt.figure(figsize=(6, 6))
        plt.pie(sizes, labels=labels, autopct='%1.1f%%')
        plt.title("Distribuição das Despesas por Categoria")
        os.makedirs("static", exist_ok=True)
        plt.savefig(grafico_path, bbox_inches="tight")
        plt.close()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

    # CAPA
    pdf.setFont("Helvetica-Bold", 28)
    pdf.drawCentredString(largura/2, altura - 5*cm, "RELATÓRIO FINANCEIRO")

    pdf.setFont("Helvetica", 14)
    pdf.drawCentredString(largura/2, altura - 7*cm, "Aluno Francisco Ribeiro — Curso Programação IEFP")

    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(largura/2, altura - 9*cm, f"Data: {datetime.now().strftime('%d/%m/%Y')}")

    pdf.saveState()
    pdf.setFont("Helvetica-Bold", 90)
    pdf.setFillGray(0.9, 0.3)
    pdf.translate(largura/2, altura/2)
    pdf.rotate(45)
    pdf.drawCentredString(0, 0, "AFinanceira")
    pdf.restoreState()

    pdf.showPage()

    # SUMÁRIO
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(2*cm, altura - 2*cm, "Sumário")

    pdf.setFont("Helvetica", 14)
    y = altura - 3.5*cm

    pagina_atual = 3
    sumario_paginas = {}

    # Entrada para gráfico
    sumario_paginas["Gráfico de Despesas"] = pagina_atual
    pdf.drawString(2*cm, y, "Gráfico de Despesas")
    pdf.drawRightString(largura - 2*cm, y, str(pagina_atual))
    y -= 1*cm
    pagina_atual += 1

    # Entrada para aportes
    sumario_paginas["Aportes (Investimentos)"] = pagina_atual
    pdf.drawString(2*cm, y, "Aportes (Investimentos)")
    pdf.drawRightString(largura - 2*cm, y, str(pagina_atual))
    y -= 1*cm
    pagina_atual += 1

    # Entradas para categorias
    for nome_cat, lista in categorias.items():
        sumario_paginas[nome_cat] = pagina_atual
        pdf.drawString(2*cm, y, nome_cat)
        pdf.drawRightString(largura - 2*cm, y, str(pagina_atual))
        y -= 1*cm
        pagina_atual += 1

    pdf.showPage()

    # PÁGINA DO GRÁFICO
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(2*cm, altura - 2*cm, "Gráfico de Despesas")

    if os.path.exists(grafico_path):
        pdf.drawImage(grafico_path, 3*cm, altura/2 - 6*cm, width=12*cm, height=12*cm)

    pdf.showPage()

    # PÁGINA DE APORTES
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(2*cm, altura - 2*cm, "Aportes (Investimentos)")

    y = altura - 3.5*cm
    pdf.setFont("Helvetica", 12)

    total_aportes = 0
    for a in historico_aportes:
        pdf.drawString(2*cm, y, f"Valor: {a['valor']} €")
        pdf.drawString(7*cm, y, f"Data: {a['data']}")
        pdf.drawString(12*cm, y, f"Mês: {a['mes_referente']}")
        total_aportes += a["valor"]
        y -= 1*cm

        if y < 3*cm:
            pdf.showPage()
            y = altura - 3*cm

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(2*cm, y - 0.5*cm, f"Total de aportes: {total_aportes:.2f} €")
    pdf.showPage()

    # TABELAS PREMIUM POR CATEGORIA
    for nome_cat, lista in categorias.items():
        pdf.setFont("Helvetica-Bold", 20)
        pdf.drawString(2*cm, altura - 2*cm, nome_cat)

        y = altura - 3.5*cm

        pdf.setFillColor(colors.HexColor("#0A2A66"))
        pdf.roundRect(2*cm, y, largura - 4*cm, 1*cm, 10, fill=True)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(2.3*cm, y + 0.35*cm, "Descrição")
        pdf.drawString(8*cm, y + 0.35*cm, "Valor (€)")
        pdf.drawString(11*cm, y + 0.35*cm, "Data")
        pdf.drawString(14*cm, y + 0.35*cm, "Mês")
        y -= 1.2*cm

        pdf.setFont("Helvetica", 11)

        cor_linha = True
        total_categoria = 0

        for item in lista:
            if cor_linha:
                pdf.setFillColor(colors.HexColor("#F2F2F2"))
                pdf.roundRect(2*cm, y, largura - 4*cm, 0.8*cm, 5, fill=True)
            cor_linha = not cor_linha

            pdf.setFillColor(colors.black)
            pdf.drawString(2.3*cm, y + 0.25*cm, str(item["descricao"]))
            pdf.drawString(8*cm, y + 0.25*cm, str(item["valor"]))
            pdf.drawString(11*cm, y + 0.25*cm, str(item["data"]))
            pdf.drawString(14*cm, y + 0.25*cm, str(item["mes_referente"]))

            total_categoria += item["valor"]
            y -= 1*cm

            if y < 3*cm:
                pdf.showPage()
                y = altura - 3*cm

        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(2*cm, y - 0.5*cm, f"Total da categoria: {total_categoria:.2f} €")

        pdf.showPage()

    pdf.save()
    buffer.seek(0)

    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=relatorio_financeiro.pdf"

    return response

# ============================================================
# LOGOUT
# ============================================================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    app.run(debug=True)
