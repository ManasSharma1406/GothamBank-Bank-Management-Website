import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import json
from pathlib import Path
import random
import string

app = Flask(__name__)

# Configuration
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-key-change-in-production'),
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=1800,  # 30 minutes
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16MB max upload
    TEMPLATES_AUTO_RELOAD=False  # Disable auto-reload in production
)

# Initialize Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.session_protection = "strong"

class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data['Account Number']
        self.name = user_data['Name']
        self.email = user_data['Email']
        self.pin = user_data['Pin']
        self.balance = user_data['Balance']

class Bank:
    database = 'data.json'
    data = []

    def __init__(self):
        if Path(self.database).exists():
            try:
                with open(self.database) as fs:
                    Bank.data = json.load(fs)
            except Exception as err:
                print(f"Error loading database: {err}")
        else:
            Bank.data = []
            self._update()

    @staticmethod
    def _update():
        with open(Bank.database, 'w') as fs:
            json.dump(Bank.data, fs, indent=4)

    @staticmethod
    def _accountgenerate():
        account_number = random.choices(string.ascii_uppercase + string.digits, k=3)
        num = random.choices(string.digits, k=3)
        id = account_number + num
        random.shuffle(id)
        return ''.join(id)

bank = Bank()

@login_manager.user_loader
def load_user(account_number):
    user_data = next((i for i in Bank.data if i['Account Number'] == account_number), None)
    if user_data:
        return User(user_data)
    return None

@app.route('/')
def index():
    # Get total number of users from the data file
    try:
        with open('data.json', 'r') as f:
            users = json.load(f)
            total_users = len(users)
    except (FileNotFoundError, json.JSONDecodeError):
        total_users = 0
    
    return render_template('index.html', total_users=total_users)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        account_identifier = request.form.get('account_identifier')
        pin = request.form.get('pin')

        user_data = None
        # Try logging in with Account Number
        if account_identifier and account_identifier.isalnum() and not '@' in account_identifier:
            user_data = next((i for i in Bank.data if i['Account Number'] == account_identifier and i['Pin'] == int(pin)), None)
        
        # If not found by Account Number, try with Email
        if not user_data and account_identifier and '@' in account_identifier:
            user_data = next((i for i in Bank.data if i['Email'] == account_identifier and i['Pin'] == int(pin)), None)

        if user_data:
            user = User(user_data)
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid account number/email or PIN')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        info = {
            "Name": request.form.get('name'),
            "Age": int(request.form.get('age')),
            "Email": request.form.get('email'),
            "Pin": int(request.form.get('pin')),
            "Account Number": Bank._accountgenerate(),
            "Balance": 0
        }

        if info['Age'] < 18 or len(str(info['Pin'])) != 4:
            flash('Invalid age or PIN format')
            return redirect(url_for('register'))

        Bank.data.append(info)
        Bank._update()
        flash('Account created successfully! Please login.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/processing_transaction')
@login_required
def processing_transaction():
    return render_template('processing.html')

@app.route('/deposit', methods=['GET', 'POST'])
@login_required
def deposit():
    if request.method == 'POST':
        amount = int(request.form.get('amount'))
        if amount > 10000 or amount <= 0:
            flash('Invalid deposit amount')
            return redirect(url_for('deposit'))
        
        user_data = next((i for i in Bank.data if i['Account Number'] == current_user.id), None)
        if user_data:
            user_data['Balance'] += amount
            Bank._update()
            flash(f'Successfully deposited ₹{amount}')
            return redirect(url_for('processing_transaction'))
    return render_template('deposit.html')

@app.route('/withdraw', methods=['GET', 'POST'])
@login_required
def withdraw():
    if request.method == 'POST':
        amount = int(request.form.get('amount'))
        user_data = next((i for i in Bank.data if i['Account Number'] == current_user.id), None)
        
        if user_data and amount <= user_data['Balance']:
            user_data['Balance'] -= amount
            Bank._update()
            flash(f'Successfully withdrew ₹{amount}')
            return redirect(url_for('processing_transaction'))
        flash('Insufficient balance')
    return render_template('withdraw.html')

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    # For development only - use a proper WSGI server like gunicorn in production
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
