from flask import Flask, Blueprint, render_template, redirect, url_for, request, flash, jsonify, make_response
from flask_login import login_user, logout_user, LoginManager, UserMixin, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import datetime
import random

db = SQLAlchemy()

app = Flask(__name__)

secret_key = secrets.token_hex(16)
app.config['SECRET_KEY'] = secret_key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
user_delayed = {}

auth = Blueprint('auth', __name__)

def DictionaryTransactions():
    dictionary_transactions = {}
    try:
      conn = db.session.connection()
      transactions = conn.execute(f'SELECT * FROM transactions_history WHERE by = ? OR forp = ?', (current_user.email, current_user.email))
    except Exception as e:
      print(e)
      errcode = e.args[0]
      error = {
        "error_code": errcode
      }
      return error
    num = 0
    for transaction in transactions:
      dictionary_transactions[f"{transaction['by']}-{num}"] = [transaction['type'], transaction['by'], transaction['forp'], transaction['value']]
      num += 1

    return dictionary_transactions

@auth.route('/login')
def login():
    try:
      current_user.id
    except:
      pass
    else:
      return redirect(url_for('main.dashboard'))
    return render_template("login.html")

@auth.route('/register')
def register():
    try:
      current_user.id
    except:
      pass
    else:
      return redirect(url_for('main.dashboard'))
    return render_template("register.html")

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))

@auth.route("/api/v1/login", methods=["POST", "GET"])
def api_login():
    email = request.form.get('email')
    password = request.form.get('password')

    user = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.password, password):
        flash('Senha ou usuário incorreto, tente novamente.')
        return redirect(url_for('auth.login'))

    login_user(user, remember=True)
    return redirect(url_for('main.dashboard'))

@auth.route("/api/v1/register", methods=["POST", "GET"])
def api_register():
    email = request.form.get('email')
    name = request.form.get('username')
    if len(name) > 16:
      flash('Use um nome de usuário menor.')
      return redirect(url_for('auth.register'))
    password = request.form.get('password')
    user = User.query.filter_by(email=email).first()
    if user:
        return redirect(url_for('auth.login'))
    new_user = User(email=email, name=name, password=generate_password_hash(password, method='sha256'))
    db.session.add(new_user)
    db.session.commit()
    return redirect(url_for('auth.login'))

app.register_blueprint(auth)

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template("index.html")

@main.route('/dashboard')
@login_required
def dashboard():
    top_3 = {}
    conn = db.session.connection()
    result = conn.execute("SELECT * FROM User ORDER BY money DESC LIMIT 3")
    for users in result:
      top_3[users['name']] = users['money']
    user = User.query.get(int(current_user.id))
    return render_template("dashboard.html", username=user.name, money=user.money, top_3=top_3, dictionary_transactions=DictionaryTransactions())

app.register_blueprint(main)

api = Blueprint('api', __name__)

@api.route('/api/v1/deposit/', methods=["POST"])
@login_required
def user_deposit():
    user = User.query.get(int(current_user.id))
    current_time = datetime.datetime.now()
    final_time = datetime.datetime.strptime("01:00:00", "%H:%M:%S")
    if current_user.id in user_delayed:
      time = final_time - (current_time - user_delayed[current_user.id])
      if user_delayed[current_user.id].hour < current_time.hour and user_delayed[current_user.id].minute <= current_time.minute:
        pass
      else:
        flash(f'Espere {time.strftime("%M minutos e %S segundos")} para fazer outro depósito.')
        return redirect(url_for('main.dashboard'))
    actual_money = user.money
    money_for_deposit = random.randint(300, 500)
    User.query.filter_by(id=current_user.id).update(dict(money=actual_money+money_for_deposit))
    new_transaction = TransactionsHistory(by=current_user.email, forp="bancohpay@felipesavazi.com", type="Depósito", value=money_for_deposit)
    db.session.add(new_transaction)
    db.session.commit()
    user_delayed[current_user.id] = current_time
    return redirect(url_for('main.dashboard'))

@api.route('/api/v1/transfer/', methods=["POST"])
@login_required
def user_transfer():
    email = request.form.get('email')
    if email == current_user.email:
      flash('Você não pode transferir para si mesmo.')
      return redirect(url_for('main.dashboard'))
    value = abs(int(request.form.get('value')))

    a_user = User.query.get(int(current_user.id))
    t_user = User.query.filter_by(email=email).first()
  
    if not t_user:
      flash('Não foi possível encontrar uma conta com o e-mail inserido.')
      return redirect(url_for('main.dashboard'))

    a_actual_money = a_user.money
    t_actual_money = t_user.money

    if value > a_actual_money:
      flash('Você não tem dinheiro suficiente para essa transação.')
      return redirect(url_for('main.dashboard'))
    User.query.filter_by(id=current_user.id).update(dict(money=a_actual_money-int(value)))
    User.query.filter_by(id=t_user.id).update(dict(money=t_actual_money+int(value)))

    new_transaction = TransactionsHistory(by=current_user.email, forp=email, type="Transferência", value=value)
    db.session.add(new_transaction)
  
    db.session.commit()

    flash(f'Transferido com sucesso para {t_user.name}.')
  
    return redirect(url_for('main.dashboard'))

@api.route('/api/v1/transactions/', methods=["POST", "GET"])
@login_required
def transactions():
    dictionary_transactions = DictionaryTransactions()
    
    return jsonify(dictionary_transactions)

@api.route('/api/v1/users/', methods=["POST", "GET"])
def users_list():
    dictionary_users = {}
    user_infos = User.query.all()
    for user in user_infos:
      dictionary_users[user.name] = [user.email, user.money]

    return jsonify(dictionary_users)

app.register_blueprint(api)

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))
    money = db.Column(db.Integer, default=0)

class TransactionsHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    by = db.Column(db.String(100))
    forp = db.Column(db.String(100))
    type = db.Column(db.String(100))
    value = db.Column(db.Integer)

@login_manager.user_loader
def load_user(user_id):
  return User.query.get(int(user_id)) 

app.run("0.0.0.0", port=8080)
