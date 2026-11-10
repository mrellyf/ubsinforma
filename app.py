
import os
from functools import wraps

import psycopg2
from psycopg2.extras import RealDictCursor

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    abort
)

from werkzeug.security import (
    check_password_hash,
    generate_password_hash
)

from dotenv import load_dotenv


load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")


# CONEXÃO COM O BANCO DE DADOS
def conectar_banco():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        database=os.getenv("DB_NAME", "ubs_informa"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        cursor_factory=RealDictCursor
    )


# VERIFICAR SE O PROFISSIONAL ESTÁ LOGADO
def profissional_logado(funcao):
    @wraps(funcao)
    def verificar(*args, **kwargs):
        if "profissional_id" not in session:
            flash("Faça login para acessar essa área.", "erro")
            return redirect(url_for("login"))

        return funcao(*args, **kwargs)

    return verificar


# PÁGINA INICIAL - ESCOLHER UBS
@app.route("/")
def inicio():
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id_ubs, nome, endereco
        FROM ubs
        ORDER BY nome
    """)

    unidades = cursor.fetchall()

    cursor.close()
    conexao.close()

    return render_template(
        "escolher_ubs.html",
        unidades=unidades
    )


# MURAL DE UMA UBS
@app.route("/ubs/<int:ubs_id>")
def mural_ubs(ubs_id):
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id_ubs, nome, endereco
        FROM ubs
        WHERE id_ubs = %s
    """, (ubs_id,))

    unidade = cursor.fetchone()

    if unidade is None:
        cursor.close()
        conexao.close()
        abort(404)

    cursor.execute("""
        SELECT
            id_mural,
            titulo,
            descricao,
            data,
            horario,
            COALESCE(categoria, 'Aviso') AS categoria,
            COALESCE(prioridade, 'Normal') AS prioridade
        FROM mural
        WHERE id_ubs = %s
        ORDER BY data DESC, horario DESC
    """, (ubs_id,))

    avisos = cursor.fetchall()

    cursor.close()
    conexao.close()

    return render_template(
        "index.html",
        unidade=unidade,
        avisos=avisos
    )


# CADASTRO DE PROFISSIONAL
@app.route("/cadastro-profissional", methods=["GET", "POST"])
def cadastro_profissional():
    conexao = conectar_banco()
    cursor = conexao.cursor()

    if request.method == "POST":
        email = request.form["email"].strip().lower()
        senha = request.form["senha"]
        id_ubs = request.form["id_ubs"]

        if len(senha) < 6:
            flash("A senha precisa ter pelo menos 6 caracteres.", "erro")

        else:
            cursor.execute("""
                SELECT id_profissional
                FROM profissional
                WHERE email = %s
            """, (email,))

            existente = cursor.fetchone()

            if existente:
                flash("Este e-mail já está cadastrado.", "erro")

            else:
                cursor.execute("""
                    SELECT id_ubs
                    FROM ubs
                    WHERE id_ubs = %s
                """, (id_ubs,))

                unidade = cursor.fetchone()

                if unidade is None:
                    flash("Selecione uma UBS válida.", "erro")

                else:
                    cursor.execute("""
                        SELECT id_profissional
                        FROM profissional
                        WHERE id_ubs = %s
                    """, (id_ubs,))

                    responsavel = cursor.fetchone()

                    if responsavel:
                        flash(
                            "Esta UBS já possui um profissional responsável cadastrado.",
                            "erro"
                        )

                    else:
                        senha_protegida = generate_password_hash(senha)

                        cursor.execute("""
                            INSERT INTO profissional
                            (email, senha, id_ubs)
                            VALUES (%s, %s, %s)
                        """, (email, senha_protegida, id_ubs))

                        conexao.commit()

                        flash(
                            "Cadastro realizado com sucesso!",
                            "sucesso"
                        )

                        cursor.close()
                        conexao.close()

                        return redirect(url_for("login"))

    cursor.execute("""
        SELECT id_ubs, nome, endereco
        FROM ubs
        ORDER BY nome
    """)

    unidades = cursor.fetchall()

    cursor.close()
    conexao.close()

    return render_template(
        "cadastro_profissional.html",
        unidades=unidades
    )


# LOGIN DO PROFISSIONAL
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        senha = request.form["senha"]

        conexao = conectar_banco()
        cursor = conexao.cursor()

        cursor.execute("""
            SELECT id_profissional, email, senha, id_ubs
            FROM profissional
            WHERE email = %s
        """, (email,))

        profissional = cursor.fetchone()

        cursor.close()
        conexao.close()

        senha_valida = False

        if profissional:
            senha_banco = profissional["senha"]

            try:
                senha_valida = check_password_hash(
                    senha_banco,
                    senha
                )
            except (ValueError, TypeError):
                senha_valida = False

            # Compatibilidade com o profissional de teste antigo.
            if not senha_valida:
                senha_valida = senha_banco == senha

        if profissional and senha_valida:
            session.clear()

            session["profissional_id"] = profissional["id_profissional"]
            session["profissional_email"] = profissional["email"]

            flash(
                "Login realizado com sucesso!",
                "sucesso"
            )

            return redirect(url_for("painel"))

        flash("E-mail ou senha incorretos.", "erro")

    return render_template("login.html")


# PAINEL DO PROFISSIONAL
@app.route("/painel")
@profissional_logado
def painel():
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id_ubs
        FROM profissional
        WHERE id_profissional = %s
    """, (session["profissional_id"],))

    profissional = cursor.fetchone()

    if profissional is None:
        cursor.close()
        conexao.close()

        session.clear()

        return redirect(url_for("login"))

    cursor.execute("""
        SELECT
            id_mural,
            titulo,
            descricao,
            data,
            horario,
            COALESCE(categoria, 'Aviso') AS categoria,
            COALESCE(prioridade, 'Normal') AS prioridade
        FROM mural
        WHERE id_ubs = %s
        ORDER BY data DESC, horario DESC
    """, (profissional["id_ubs"],))

    avisos = cursor.fetchall()

    cursor.close()
    conexao.close()

    return render_template(
        "painel.html",
        avisos=avisos
    )


# PUBLICAR NOVO AVISO
@app.route("/avisos/novo", methods=["POST"])
@profissional_logado
def novo_aviso():
    titulo = request.form["titulo"]
    descricao = request.form["descricao"]
    data = request.form["data"]
    horario = request.form["horario"]
    categoria = request.form["categoria"]
    prioridade = request.form["prioridade"]

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id_ubs
        FROM profissional
        WHERE id_profissional = %s
    """, (session["profissional_id"],))

    profissional = cursor.fetchone()

    if profissional is None:
        cursor.close()
        conexao.close()

        session.clear()

        return redirect(url_for("login"))

    cursor.execute("""
        INSERT INTO mural (
            titulo,
            descricao,
            data,
            horario,
            id_ubs,
            id_profissional,
            categoria,
            prioridade
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        titulo,
        descricao,
        data,
        horario,
        profissional["id_ubs"],
        session["profissional_id"],
        categoria,
        prioridade
    ))

    conexao.commit()

    cursor.close()
    conexao.close()

    flash(
        "Aviso publicado com sucesso!",
        "sucesso"
    )

    return redirect(url_for("painel"))


# REMOVER AVISO
@app.route("/avisos/<int:aviso_id>/remover", methods=["POST"])
@profissional_logado
def remover_aviso(aviso_id):
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        DELETE FROM mural
        WHERE id_mural = %s
        AND id_ubs = (
            SELECT id_ubs
            FROM profissional
            WHERE id_profissional = %s
        )
    """, (
        aviso_id,
        session["profissional_id"]
    ))

    conexao.commit()

    cursor.close()
    conexao.close()

    flash(
        "Aviso removido com sucesso!",
        "sucesso"
    )

    return redirect(url_for("painel"))


# SAIR DA CONTA
@app.route("/sair")
def sair():
    session.clear()

    flash(
        "Você saiu da sua conta.",
        "sucesso"
    )

    return redirect(url_for("inicio"))


# INICIAR SISTEMA
if __name__ == "__main__":
    app.run(debug=True)
