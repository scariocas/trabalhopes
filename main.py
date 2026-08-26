from flask import Flask, render_template, request, redirect, session,  jsonify
from database import get_db_connection
from datetime import date

# Cria uma instância da aplicação Flask
app = Flask(__name__)

# CHAVE SECRETA DA SESSÃO
app.secret_key = "hotel_bygirls_123"

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

# Rota para login do usuário
@app.route('/loginusuario', methods=['GET', 'POST'])
def login():

    # Quando apenas abrir a página de login
    if request.method == 'GET':
        return render_template("loginusuario.html")

    # Quando clicar no botão Entrar
    email = request.form['email'].strip()
    senha = request.form['senha']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT *
            FROM usuario
            WHERE email = %s AND senha = %s
        """, (email, senha))

        usuario = cursor.fetchone()

    except Exception as e:

        return render_template(
            "loginusuario.html",
            mensagem_erro=f"Erro ao realizar login: {e}"
        )

    finally:

        cursor.close()
        conn.close()

    # Se encontrou o usuário
    if usuario:

        # Guarda informações do usuário na sessão
        session['usuario'] = usuario['nome']
        session['idUsuario'] = usuario['idUsuario']

        return redirect('/')

    # Se não encontrou
    else:

        return render_template(
            "loginusuario.html",
            mensagem_erro="E-mail ou senha inválidos."
        )

# Rota para cadastro de reserva
@app.route('/cadreserva', methods=['GET', 'POST'])
def cadreserva():
    if 'usuario' not in session:
        return redirect('/loginusuario')

    if request.method == 'GET':
        return render_template("cadreserva.html")

    # Recebe os dados do formulário
    checkin = request.form['checkin']
    checkout = request.form['checkout']
    hospedes = int(request.form['hospedes'])
    quarto = request.form['quarto']
    valorDiaria = request.form['valorDiaria']
    valorTotal = request.form['valorTotal']
    observacoes = request.form.get('observacoes', '').strip()

    temCriancas = request.form.get('temCriancas', 'nao')
    criancas = int(request.form.get('quantidadeCriancas', 0) or 0)
    idadesCriancas = request.form.get('idadesCriancas', '').strip()

    idades = []

    if temCriancas == 'sim':
        if criancas <= 0:
            return render_template("cadreserva.html", mensagem_erro="Informe a quantidade de crianças.")
        if not idadesCriancas:
            return render_template("cadreserva.html", mensagem_erro="Informe a idade de todas as crianças.")

        try:
            idades = [int(idade) for idade in idadesCriancas.split(',') if idade.strip() != '']
        except ValueError:
            return render_template("cadreserva.html", mensagem_erro="As idades das crianças devem ser números.")

        if len(idades) != criancas:
            return render_template("cadreserva.html", mensagem_erro="Informe a idade de todas as crianças.")

        for idade in idades:
            if idade < 0 or idade > 17:
                return render_template("cadreserva.html", mensagem_erro="Informe idades válidas para as crianças (0 a 17 anos).")
    else:
        criancas = 0
        idades = []

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Busca disponibilidade para garantir que não haverá overbooking
        cursor.execute("SELECT idQuarto, tipo, quantidade, valorDiaria FROM quarto")
        quartos = cursor.fetchall()

        disponibilidade = {}
        for q in quartos:
            cursor.execute("""
                SELECT COALESCE(SUM(rq.quantidade), 0) AS reservados
                FROM reserva_quarto rq
                INNER JOIN reserva r ON rq.idReserva = r.idReserva
                WHERE rq.idQuarto = %s AND r.checkin < %s AND r.checkout > %s
                AND (r.cancelada = 0 OR r.cancelada IS NULL)
            """, (q['idQuarto'], checkout, checkin))

            resultado = cursor.fetchone()
            disponibilidade[q['idQuarto']] = q['quantidade'] - resultado['reservados']

        partes = [parte.strip() for parte in quarto.split("+")]
        quartos_escolhidos = []

        for parte in partes:
            palavras = parte.split()
            if len(palavras) < 2:
                raise Exception("Opção de quarto inválida.")

            quantidade = int(palavras[0])
            tipo = " ".join(palavras[1:]).strip()

            cursor.execute("SELECT idQuarto, tipo, quantidade, valorDiaria FROM quarto WHERE LOWER(tipo) = LOWER(%s)", (tipo,))
            q = cursor.fetchone()

            if not q:
                raise Exception(f"O tipo de quarto '{tipo}' não foi encontrado.")

            idQuarto = q['idQuarto']

            if disponibilidade[idQuarto] < quantidade:
                raise Exception(f"Não há quartos {q['tipo']} suficientes para essas datas.")

            quartos_escolhidos.append({
                'idQuarto': idQuarto,
                'quantidade': quantidade
            })

        # Grava a Reserva no Banco de Dados
        cursor.execute("""
            INSERT INTO reserva
            (idUsuario, checkin, checkout, hospedes, criancas, quarto, valorDiaria, dataReserva, valorTotal, observacoes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s)
        """, (
            session['idUsuario'],
            checkin,
            checkout,
            hospedes,
            criancas,
            quarto,
            valorDiaria,
            valorTotal,
            observacoes
        ))

        idReserva = cursor.lastrowid

        for item in quartos_escolhidos:
            cursor.execute("""
                INSERT INTO reserva_quarto (idReserva, idQuarto, quantidade)
                VALUES (%s, %s, %s)
            """, (idReserva, item['idQuarto'], item['quantidade']))

        conn.commit()
        return render_template("cadreserva.html", mensagem_sucesso="Reserva cadastrada com sucesso!")

    except Exception as e:
        conn.rollback()
        return render_template("cadreserva.html", mensagem_erro=f"Erro ao cadastrar reserva: {e}")

    finally:
        cursor.close()
        conn.close()
# Rota para disponibilidade dos quartos
@app.route('/api/opcoes-quartos')
def opcoes_quartos():
    if 'usuario' not in session:
        return jsonify({
            'sucesso': False,
            'mensagem': 'Usuário não está logado.'
        }), 401

    # Recebe os dados
    checkin = request.args.get('checkin')
    checkout = request.args.get('checkout')
    hospedesTexto = request.args.get('hospedes', '0')
    criancasTexto = request.args.get('criancas', '0')
    idadesTexto = request.args.get('idades', '')

    # Verifica as datas
    if not checkin or not checkout:
        return jsonify({
            'sucesso': False,
            'mensagem': 'Informe as datas.'
        })

    if checkout <= checkin:
        return jsonify({
            'sucesso': False,
            'mensagem': 'O check-out deve ser posterior ao check-in.'
        })

    # Converte o total de hóspedes e crianças
    try:
        totalHospedes = int(hospedesTexto)
        criancas = int(criancasTexto)
    except ValueError:
        return jsonify({
            'sucesso': False,
            'mensagem': 'Quantidade de hóspedes inválida.'
        })

    if totalHospedes <= 0:
        return jsonify({
            'sucesso': False,
            'mensagem': 'Informe pelo menos um hóspede.'
        })

    if criancas < 0:
        return jsonify({
            'sucesso': False,
            'mensagem': 'Quantidade de crianças inválida.'
        })

    if criancas > totalHospedes:
        return jsonify({
            'sucesso': False,
            'mensagem': 'A quantidade de crianças não pode ser maior que o total de hóspedes.'
        })

    # Calcula a quantidade de adultos
    adultos = totalHospedes - criancas

    # Processa as idades das crianças
    idades = []
    if criancas > 0:
        if not idadesTexto:
            return jsonify({
                'sucesso': False,
                'mensagem': 'Informe a idade de todas as crianças.'
            })

        try:
            idades = [
                int(idade)
                for idade in idadesTexto.split(',')
                if idade.strip() != ''
            ]
        except ValueError:
            return jsonify({
                'sucesso': False,
                'mensagem': 'Idade de criança inválida.'
            })

        if len(idades) != criancas:
            return jsonify({
                'sucesso': False,
                'mensagem': 'Informe a idade de todas as crianças.'
            })

    for idade in idades:
        if idade < 0 or idade > 17:
            return jsonify({
                'sucesso': False,
                'mensagem': 'As idades devem estar entre 0 e 17 anos.'
            })

    # Regra de negócio: Crianças até 5 anos geram R$ 100 de desconto
    criancasNaoPagantes = sum(1 for idade in idades if idade <= 5)
    criancasPagantes = sum(1 for idade in idades if idade > 5)
    totalPagantes = adultos + criancasPagantes
    descontoDiaria = criancasNaoPagantes * 100

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                idQuarto,
                tipo,
                quantidade,
                valorDiaria
            FROM quarto
        """)
        quartos = cursor.fetchall()

        disponibilidade = {}
        for quartoBanco in quartos:
            cursor.execute("""
                SELECT COALESCE(SUM(rq.quantidade), 0) AS reservados
                FROM reserva_quarto rq
                INNER JOIN reserva r ON rq.idReserva = r.idReserva
                WHERE rq.idQuarto = %s
                AND r.checkin < %s
                AND r.checkout > %s
                AND (r.cancelada = 0 OR r.cancelada IS NULL)
            """, (
                quartoBanco['idQuarto'],
                checkout,
                checkin
            ))

            resultado = cursor.fetchone()
            reservados = resultado['reservados'] or 0
            disponiveis = quartoBanco['quantidade'] - reservados
            disponibilidade[quartoBanco['idQuarto']] = max(disponiveis, 0)

        # Mapeamento dinâmico de capacidades
        tiposQuarto = []
        for quartoBanco in quartos:
            nome = quartoBanco['tipo'].strip().lower()

            # Mapeia capacidade conforme a palavra-chave no nome do quarto
            if 'solteiro' in nome:
                capacidade = 1
            elif 'casal' in nome:
                capacidade = 2
            elif 'triplo' in nome:
                capacidade = 3
            elif 'suite' in nome or 'suíte' in nome:
                capacidade = 4
            else:
                capacidade = 1

            # CONVERSÃO ESSENCIAL: Converte o tipo Decimal do MySQL para float para não quebrar o jsonify
            preco_float = float(quartoBanco['valorDiaria'])

            tiposQuarto.append({
                'idQuarto': quartoBanco['idQuarto'],
                'tipo': quartoBanco['tipo'],
                'capacidade': capacidade,
                'disponiveis': disponibilidade[quartoBanco['idQuarto']],
                'preco': preco_float
            })

        # Gera combinações de quartos disponíveis para atender o total de hóspedes
        combinacoes = []

        def gerar_combinacoes(indice, pessoasAtendidas, quartosSelecionados, precoTotal):
            if pessoasAtendidas >= totalHospedes:
                precoComDesconto = max(precoTotal - descontoDiaria, 0)
                combinacoes.append({
                    'quartos': quartosSelecionados.copy(),
                    'preco': precoComDesconto,
                    'precoOriginal': precoTotal,
                    'capacidade': pessoasAtendidas
                })
                return

            if indice >= len(tiposQuarto):
                return

            quartoAtual = tiposQuarto[indice]

            # Opção 1: Não utilizar este tipo
            gerar_combinacoes(indice + 1, pessoasAtendidas, quartosSelecionados, precoTotal)

            # Opção 2: Utilizar este tipo (se houver disponível)
            maxQuantidade = min(quartoAtual['disponiveis'], totalHospedes)
            for quantidade in range(1, maxQuantidade + 1):
                novaCapacidade = pessoasAtendidas + (quartoAtual['capacidade'] * quantidade)
                novoPreco = precoTotal + (quartoAtual['preco'] * quantidade)

                descricao = f"1 {quartoAtual['tipo']}" if quantidade == 1 else f"{quantidade} Quartos {quartoAtual['tipo']}"

                quartosSelecionados.append({
                    'tipo': quartoAtual['tipo'],
                    'quantidade': quantidade,
                    'idQuarto': quartoAtual['idQuarto'],
                    'descricao': descricao
                })

                gerar_combinacoes(indice + 1, novaCapacidade, quartosSelecionados, novoPreco)
                quartosSelecionados.pop()

        gerar_combinacoes(0, 0, [], 0)

        # Remove combinações duplicadas
        opcoesUnicas = {}
        for combinacao in combinacoes:
            descricao = " + ".join(item['descricao'] for item in combinacao['quartos'])
            if descricao not in opcoesUnicas:
                opcoesUnicas[descricao] = {
                    'descricao': descricao,
                    'preco': combinacao['preco'],
                    'precoOriginal': combinacao['precoOriginal'],
                    'capacidade': combinacao['capacidade']
                }

        opcoes = list(opcoesUnicas.values())
        opcoes.sort(key=lambda x: (x['preco'], x['capacidade']))

        return jsonify({
            'sucesso': True,
            'totalHospedes': totalHospedes,
            'adultos': adultos,
            'criancas': criancas,
            'criancasPagantes': criancasPagantes,
            'criancasNaoPagantes': criancasNaoPagantes,
            'totalPagantes': totalPagantes,
            'descontoDiaria': descontoDiaria,
            'opcoes': opcoes
        })

    except Exception as e:
        return jsonify({
            'sucesso': False,
            'mensagem': f'Erro ao verificar disponibilidade: {e}'
        }), 500

    finally:
        cursor.close()
        conn.close()
#rota para consulta de cadastro de reserva
@app.route('/consultareserva')
def consultareserva():

    if 'usuario' not in session:
        return redirect('/loginusuario')
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                r.idReserva,
                u.nome,
                r.checkin,
                r.checkout,
                r.hospedes,
                r.quarto,
                r.valorDiaria,
                r.valorTotal,
                r.dataReserva
            FROM reserva r
            INNER JOIN usuario u
                ON r.idUsuario = u.idUsuario
            ORDER BY r.checkin
        """)

        reservas = cursor.fetchall()

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


def buscar_disponibilidade(checkin, checkout):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                q.idQuarto,
                q.tipo,
                q.quantidade,
                q.valorDiaria,

                COALESCE(SUM(
                    CASE
                        WHEN r.idReserva IS NOT NULL
                        AND r.checkin < %s
                        AND r.checkout > %s
                        AND (r.cancelada = 0 OR r.cancelada IS NULL)
                        THEN rq.quantidade
                        ELSE 0
                    END
                ), 0) AS reservados

            FROM quarto q

            LEFT JOIN reserva_quarto rq
                ON q.idQuarto = rq.idQuarto

            LEFT JOIN reserva r
                ON rq.idReserva = r.idReserva

            GROUP BY
                q.idQuarto,
                q.tipo,
                q.quantidade,
                q.valorDiaria

            ORDER BY q.idQuarto
        """, (checkout, checkin))

        quartos = cursor.fetchall()

        for quarto in quartos:
            quarto['disponiveis'] = (
                    quarto['quantidade'] - quarto['reservados']
            )

        return quartos

    finally:

        cursor.close()
        conn.close()

# Ponto de entrada da aplicação
if __name__ == '__main__':
    # Inicia o servidor Flask em modo de desenvolvimento
    app.run(debug=True)