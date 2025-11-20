from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import date

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///futebol.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ------------------ MODELOS ------------------ #

class Jogador(db.Model):
    __tablename__ = 'jogadores'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    goleiro = db.Column(db.Boolean, default=False)  # indica se é goleiro

    def __repr__(self):
        return f'<Jogador {self.nome}>'


class Partida(db.Model):
    __tablename__ = 'partidas'
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False, unique=True)

    def __repr__(self):
        return f'<Partida {self.data}>'


class Estatistica(db.Model):
    __tablename__ = 'estatisticas'
    id = db.Column(db.Integer, primary_key=True)
    partida_id = db.Column(db.Integer, db.ForeignKey('partidas.id'), nullable=False)
    jogador_id = db.Column(db.Integer, db.ForeignKey('jogadores.id'), nullable=False)

    gols = db.Column(db.Integer, default=0)
    assistencias = db.Column(db.Integer, default=0)
    vitorias = db.Column(db.Integer, default=0)
    empates = db.Column(db.Integer, default=0)

    # métrica extra para goleiro
    sem_gol = db.Column(db.Integer, default=0)  # partidas sem tomar gol

    partida = db.relationship('Partida', backref='estatisticas')
    jogador = db.relationship('Jogador', backref='estatisticas')

    @property
    def pontos_dia(self):
        """
        Jogador de linha:
            gol, assistência, vitória = 2 pts
            empate = 1 pt

        Goleiro:
            sem_gol, vitória, assistência, gol = 2 pts cada
            (não conta empate)
        """
        if self.jogador and self.jogador.goleiro:
            return 2 * (
                (self.sem_gol or 0)
                + (self.vitorias or 0)
                + (self.assistencias or 0)
                + (self.gols or 0)
            )
        else:
            return (
                2 * (self.gols or 0)
                + 2 * (self.assistencias or 0)
                + 2 * (self.vitorias or 0)
                + 1 * (self.empates or 0)
            )


# cria as tabelas ao iniciar a aplicação (se não existirem)
with app.app_context():
    db.create_all()


# ------------------ ROTAS ------------------ #

@app.route('/', methods=['GET', 'POST'])
def index():
    # Data escolhida (padrão = hoje)
    data_str = request.args.get('data')
    if data_str:
        ano, mes, dia = map(int, data_str.split('-'))
        data_partida = date(ano, mes, dia)
    else:
        data_partida = date.today()

    # Garante que exista uma Partida para essa data
    partida = Partida.query.filter_by(data=data_partida).first()
    if not partida:
        partida = Partida(data=data_partida)
        db.session.add(partida)
        db.session.commit()

    # todos os jogadores
    jogadores = Jogador.query.order_by(Jogador.nome).all()
    goleiros = [j for j in jogadores if j.goleiro]
    jogadores_linha = [j for j in jogadores if not j.goleiro]

    # Salvando estatísticas (POST)
    if request.method == 'POST':
        for jogador in jogadores:
            prefix = f'j{jogador.id}_'

            def get_int(nome_campo):
                val = request.form.get(prefix + nome_campo, '0')
                try:
                    return int(val)
                except ValueError:
                    return 0

            gols = get_int('gols')
            assist = get_int('assistencias')
            vits = get_int('vitorias')
            emp = get_int('empates')
            sem_gol = get_int('sem_gol')

            estat = Estatistica.query.filter_by(
                partida_id=partida.id,
                jogador_id=jogador.id
            ).first()

            if not estat:
                estat = Estatistica(
                    partida_id=partida.id,
                    jogador_id=jogador.id
                )
                db.session.add(estat)

            estat.gols = gols
            estat.assistencias = assist
            estat.vitorias = vits
            estat.empates = emp
            estat.sem_gol = sem_gol

        db.session.commit()
        return redirect(url_for('index', data=data_partida.isoformat()))

    # Estatísticas do dia por jogador
    estat_por_jogador = {}
    for jogador in jogadores:
        estat = Estatistica.query.filter_by(
            partida_id=partida.id,
            jogador_id=jogador.id
        ).first()
        estat_por_jogador[jogador.id] = estat

    # Ranking acumulado (todas as partidas)
    ranking = []
    for jogador in jogadores:
        total_gols = 0
        total_assist = 0
        total_vits = 0
        total_emp = 0
        total_sem_gol = 0
        total_pontos = 0

        for est in jogador.estatisticas:
            total_gols += est.gols or 0
            total_assist += est.assistencias or 0
            total_vits += est.vitorias or 0
            total_emp += est.empates or 0
            total_sem_gol += est.sem_gol or 0
            total_pontos += est.pontos_dia

        ranking.append({
            "jogador": jogador,
            "gols": total_gols,
            "assistencias": total_assist,
            "vitorias": total_vits,
            "empates": total_emp,
            "sem_gol": total_sem_gol,
            "pontos": total_pontos,
        })

    ranking.sort(key=lambda x: x["pontos"], reverse=True)

    return render_template(
        'index.html',
        partida=partida,
        goleiros=goleiros,
        jogadores_linha=jogadores_linha,
        estat_por_jogador=estat_por_jogador,
        ranking=ranking
    )


@app.route('/jogadores', methods=['GET', 'POST'])
def jogadores_view():
    if request.method == 'POST':
        nome = request.form.get('nome')
        goleiro = bool(request.form.get('goleiro'))
        if nome:
            j = Jogador(nome=nome, goleiro=goleiro)
            db.session.add(j)
            db.session.commit()
        return redirect(url_for('jogadores_view'))

    lista = Jogador.query.order_by(Jogador.nome).all()
    return render_template('jodadores.html', jogadores=lista)



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005, debug=True)
