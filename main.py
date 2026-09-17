from flask import Flask, render_template, request, redirect, session
from database import get_db_connection  #Importa a função de conexão com o banco de dados#
from datetime import date

# Cria uma instância da aplicação Flask
app = Flask(__name__)

app.secret_key = 'senhasecreta'


# Rota principal que exibe o menu
@app.route('/')
def index():
    return render_template('menu.html', titulo="Hotel ByGirls")

#rota para cadastro de usuario
@app.route('/usuario', methods=['GET', 'POST'])
def usuario():

    if request.method == 'POST':

        nome = request.form['nome'].strip()
        cpf = request.form['cpf'].strip()
        telefone = request.form['telefone'].strip()
        email = request.form['email'].strip()
        senha = request.form['senha']

        conn = get_db_connection()
        cursor = conn.cursor()

        try:

            cursor.execute("""
                INSERT INTO usuario
                (nome, cpf, telefone, email, senha)
                VALUES (%s,%s,%s,%s,%s)
            """,(nome, cpf, telefone, email, senha))

            conn.commit()

            mensagem = "Usuário cadastrado com sucesso!"

        except Exception as e:

            conn.rollback()
            mensagem = f"Erro: {e}"

        finally:

            conn.close()

        return render_template(
            "usuario.html",
            mensagem_sucesso=mensagem
        )

    return render_template("usuario.html")

#rota para login do usuario
@app.route('/loginusuario', methods=['GET','POST'])
def login():

    if request.method == 'POST':

        email = request.form['email']
        senha = request.form['senha']


        conn = get_db_connection()

        cursor = conn.cursor(dictionary=True)


        cursor.execute("""
            SELECT *
            FROM usuario
            WHERE email=%s AND senha=%s
        """,
        (email, senha))


        usuario = cursor.fetchone()


        conn.close()


        if usuario:

            session['usuario'] = usuario['nome']
            session['idUsuario'] = usuario['idUsuario']


            return redirect('/')


        else:

            return render_template(
                'loginusuario.html',
                mensagem_erro="E-mail ou senha inválidos."
            )

    return render_template("loginusuario.html")

# Rota para cadastro de reserva
@app.route('/cadreserva', methods=['GET', 'POST'])
def cadreserva():

    if 'usuario' not in session:
        return redirect('/login')

    id_usuario = session['idUsuario']


    if request.method == 'POST':

        checkin = request.form['checkin']
        checkout = request.form['checkout']
        hospedes = request.form['hospedes']
        quarto = request.form['tipoquarto']
        valorDiaria = request.form['valorDiaria']
        valorTotal = request.form['valorTotal']
        observacoes = request.form.get('observacoes','')

        conn = get_db_connection()
        cursor = conn.cursor()

        try:

            cursor.execute("""
                INSERT INTO reserva
                (idUsuario, checkin, checkout, hospedes, quarto, valorDiaria, valorTotal, observacoes)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
            id_usuario,
            checkin,
            checkout,
            hospedes,
            quarto,
            valorDiaria,
            valorTotal,
            observacoes
            ))


            conn.commit()

            mensagem="Reserva cadastrada com sucesso!"


        except Exception as e:

            conn.rollback()

            mensagem=f"Erro: {e}"


        finally:

            conn.close()


            return render_template(
                "cadreserva.html",
                mensagem_sucesso=mensagem
            )

    return render_template("cadreserva.html")

#rota para consulta de cadastro de reserva
@app.route('/consultareserva')
def consultareserva():

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                u.nome,
                r.checkin,
                r.checkout,
                r.hospedes,
                r.quarto,
                r.observacoes
            FROM reserva r
            INNER JOIN usuario u
                ON r.idUsuario = u.idUsuario
            ORDER BY r.checkin
        """)

        reservas = cursor.fetchall()

        conn.close()

        return render_template(
            "consultareserva.html",
            reservas=reservas
        )

    except Exception as e:
        return render_template(
            "consultareserva.html",
            mensagem_erro=str(e)
        )
#rota para sair do login
@app.route('/logout')
def logout():

    session.clear()   # Remove os dados da sessão

    return redirect('/')

# Ponto de entrada da aplicação
if __name__ == '__main__':
    # Inicia o servidor Flask em modo de desenvolvimento
    app.run(debug=True)