
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
    database_url = os.getenv("DATABASE_URL")
    print("DATABASE_URL encontrada:", bool(database_url))
    
    if database_url:
        return psycopg2.connect(
            database_url,
            cursor_factory=RealDictCursor
        )

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
# VERIFICAR SE O ADMINISTRADOR ESTÁ LOGADO
def administrador_logado(funcao):
    @wraps(funcao)
    def verificar(*args, **kwargs):
        if "administrador_id" not in session:
            flash("Faça login como administrador para acessar essa área.", "erro")
            return redirect(url_for("login_administrador"))

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

# CADASTRO PÚBLICO DESATIVADO
@app.route("/cadastro-profissional", methods=["GET", "POST"])
def cadastro_profissional():
    flash(
        "Os acessos são criados exclusivamente pelo administrador.",
        "erro"
    )
    return redirect(url_for("login"))

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

# LOGIN DO ADMINISTRADOR
@app.route("/admin/login", methods=["GET", "POST"])
def login_administrador():

    if request.method == "POST":
        email = request.form["email"].strip().lower()
        senha = request.form["senha"]

        conexao = conectar_banco()
        cursor = conexao.cursor()

        cursor.execute("""
            SELECT id_administrador, nome, email, senha
            FROM administrador
            WHERE email = %s
        """, (email,))

        administrador = cursor.fetchone()

        cursor.close()
        conexao.close()

        if administrador and check_password_hash(
            administrador["senha"], senha
        ):
            session.clear()

            session["administrador_id"] = administrador["id_administrador"]
            session["administrador_nome"] = administrador["nome"]

            flash("Login realizado com sucesso!", "sucesso")
            return redirect(url_for("painel_administrador"))

        flash("E-mail ou senha incorretos.", "erro")

    return render_template("login_administrador.html")


# PAINEL DO ADMINISTRADOR
@app.route("/admin/painel")
@administrador_logado
def painel_administrador():

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT
            u.id_ubs,
            u.nome,
            u.endereco,
            p.id_profissional,
            p.email
        FROM ubs u
        LEFT JOIN profissional p
            ON u.id_ubs = p.id_ubs
        ORDER BY u.nome
    """)

    unidades = cursor.fetchall()

    cursor.close()
    conexao.close()

    return render_template(
        "painel_administrador.html",
        unidades=unidades
    )

# SAIR DA CONTA DO ADMINISTRADOR
@app.route("/admin/sair")
@administrador_logado
def sair_administrador():

    session.clear()

    flash("Você saiu da conta administrativa.", "sucesso")
    return redirect(url_for("inicio"))   

# CADASTRAR UBS E CRIAR SEU ACESSO
@app.route("/admin/ubs/nova", methods=["POST"])
@administrador_logado
def cadastrar_ubs():

    nome = request.form["nome"].strip()
    endereco = request.form["endereco"].strip()
    email = request.form["email"].strip().lower()
    senha = request.form["senha"]

    if len(senha) < 6:
        flash("A senha precisa ter pelo menos 6 caracteres.", "erro")
        return redirect(url_for("painel_administrador"))

    conexao = conectar_banco()
    cursor = conexao.cursor()

    try:
        cursor.execute("""
            SELECT id_profissional
            FROM profissional
            WHERE email = %s
        """, (email,))

        if cursor.fetchone():
            flash("Este e-mail já está sendo utilizado.", "erro")
            return redirect(url_for("painel_administrador"))

        cursor.execute("""
            INSERT INTO ubs (nome, endereco)
            VALUES (%s, %s)
            RETURNING id_ubs
        """, (nome, endereco))

        nova_ubs = cursor.fetchone()
        id_ubs = nova_ubs["id_ubs"]

        senha_protegida = generate_password_hash(senha)

        cursor.execute("""
            INSERT INTO profissional (email, senha, id_ubs)
            VALUES (%s, %s, %s)
        """, (email, senha_protegida, id_ubs))

        conexao.commit()

        flash("UBS cadastrada e acesso criado com sucesso!", "sucesso")

    except Exception:
        conexao.rollback()
        flash("Não foi possível cadastrar a UBS. Verifique os dados.", "erro")

    finally:
        cursor.close()
        conexao.close()

    return redirect(url_for("painel_administrador")) 


# REDEFINIR SENHA DE UMA UBS
@app.route("/admin/ubs/<int:profissional_id>/redefinir-senha", methods=["GET", "POST"])
@administrador_logado
def redefinir_senha_ubs(profissional_id):

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT p.id_profissional, p.email, u.nome
        FROM profissional p
        JOIN ubs u ON p.id_ubs = u.id_ubs
        WHERE p.id_profissional = %s
    """, (profissional_id,))

    profissional = cursor.fetchone()

    if profissional is None:
        cursor.close()
        conexao.close()
        flash("Acesso não encontrado.", "erro")
        return redirect(url_for("painel_administrador"))

    if request.method == "POST":

        senha = request.form["senha"]

        if len(senha) < 6:
            flash("A senha precisa ter pelo menos 6 caracteres.", "erro")
        else:
            senha_protegida = generate_password_hash(senha)

            cursor.execute("""
                UPDATE profissional
                SET senha = %s
                WHERE id_profissional = %s
            """, (senha_protegida, profissional_id))

            conexao.commit()

            cursor.close()
            conexao.close()

            flash("Senha redefinida com sucesso!", "sucesso")
            return redirect(url_for("painel_administrador"))

    cursor.close()
    conexao.close()

    return render_template(
        "redefinir_senha_ubs.html",
        profissional=profissional
    )

# ALTERAR E-MAIL DE ACESSO DE UMA UBS
@app.route("/admin/profissional/<int:profissional_id>/email", methods=["GET", "POST"])
@administrador_logado
def alterar_email_ubs(profissional_id):

    conexao = conectar_banco()
    cursor = conexao.cursor()

    try:
        cursor.execute("""
            SELECT p.id_profissional, p.email, u.nome
            FROM profissional p
            JOIN ubs u ON p.id_ubs = u.id_ubs
            WHERE p.id_profissional = %s
        """, (profissional_id,))

        profissional = cursor.fetchone()

        if profissional is None:
            flash("Acesso profissional não encontrado.", "erro")
            return redirect(url_for("painel_administrador"))

        if request.method == "POST":

            novo_email = request.form["email"].strip().lower()

            if not novo_email:
                flash("Informe um e-mail válido.", "erro")

            else:
                cursor.execute("""
                    SELECT id_profissional
                    FROM profissional
                    WHERE email = %s
                    AND id_profissional <> %s
                """, (novo_email, profissional_id))

                if cursor.fetchone():
                    flash("Este e-mail já está sendo utilizado.", "erro")

                else:
                    cursor.execute("""
                        UPDATE profissional
                        SET email = %s
                        WHERE id_profissional = %s
                    """, (novo_email, profissional_id))

                    conexao.commit()
                    flash("E-mail atualizado com sucesso!", "sucesso")
                    return redirect(url_for("painel_administrador"))

        return render_template(
            "alterar_email_ubs.html",
            profissional=profissional
        )

    except Exception:
        conexao.rollback()
        flash("Não foi possível atualizar o e-mail.", "erro")
        return redirect(url_for("painel_administrador"))

    finally:
        cursor.close()
        conexao.close()



# REMOVER UMA UBS E SEUS REGISTROS
@app.route("/admin/ubs/<int:ubs_id>/remover", methods=["POST"])
@administrador_logado
def remover_ubs(ubs_id):

    conexao = conectar_banco()
    cursor = conexao.cursor()

    try:
        cursor.execute("""
            SELECT nome
            FROM ubs
            WHERE id_ubs = %s
        """, (ubs_id,))

        unidade = cursor.fetchone()

        if unidade is None:
            flash("UBS não encontrada.", "erro")
            return redirect(url_for("painel_administrador"))

        # Remove primeiro os avisos da unidade
        cursor.execute("""
            DELETE FROM mural
            WHERE id_ubs = %s
        """, (ubs_id,))

        # Remove o acesso profissional
        cursor.execute("""
            DELETE FROM profissional
            WHERE id_ubs = %s
        """, (ubs_id,))

        # Por último, remove a UBS
        cursor.execute("""
            DELETE FROM ubs
            WHERE id_ubs = %s
        """, (ubs_id,))

        conexao.commit()

        flash(
            f"A UBS {unidade['nome']} e seus registros foram removidos.",
            "sucesso"
        )

    except Exception:
        conexao.rollback()
        flash("Não foi possível remover a UBS.", "erro")

    finally:
        cursor.close()
        conexao.close()

    return redirect(url_for("painel_administrador"))



# INICIAR SISTEMA
if __name__ == "__main__":
    app.run(debug=True)

    
