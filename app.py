# FileMarket - All in One
# Copiez ce fichier dans votre repo et c'est tout!

from flask import Flask, jsonify, request, session, render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import 
import os
import bcrypt
import stripe
import boto3
import uuid
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///filemarket.db')
app.config['MAX_CONTENT_LENGTH'] = 10737418240

db = SQLAlchemy(app)
CORS(app)

# Créer les tables automatiquement
with app.app_context():
    db.create_all()

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

s3 = boto3.client('s3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION', 'eu-west-1')
)

# ========== MODELS ==========

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    username = db.Column(db.String(100), unique=True)
    paypal_email = db.Column(db.String(255))
    is_admin = db.Column(db.Boolean, default=False)
    balance = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, pwd):
        self.password_hash = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
    def check_password(self, pwd):
        return bcrypt.checkpw(pwd.encode(), self.password_hash.encode())

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    filename = db.Column(db.String(255))
    s3_key = db.Column(db.String(255))
    file_size = db.Column(db.BigInteger)
    price = db.Column(db.Float)
    description = db.Column(db.Text)
    downloads = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    owner = db.relationship('User', backref='files')

class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    file_id = db.Column(db.Integer, db.ForeignKey('file.id'))
    amount = db.Column(db.Float)
    stripe_id = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    buyer = db.relationship('User', foreign_keys=[buyer_id])
    seller = db.relationship('User', foreign_keys=[seller_id])
    file = db.relationship('File')

class AdminSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    commission = db.Column(db.Float, default=20)

# ========== ROUTES ==========

@app.route('/')
def index():
    return '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FileMarket - Vendre des fichiers</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI'; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; flex-direction: column; }
        nav { background: rgba(0,0,0,0.2); color: white; padding: 20px; display: flex; justify-content: space-between; align-items: center; }
        nav h1 { font-size: 28px; }
        nav a { color: white; margin: 0 15px; text-decoration: none; }
        .hero { flex: 1; display: flex; justify-content: center; align-items: center; text-align: center; color: white; }
        .hero h2 { font-size: 48px; margin-bottom: 20px; }
        .hero p { font-size: 20px; margin-bottom: 30px; }
        .btn { background: white; color: #667eea; padding: 15px 30px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; margin: 10px; font-weight: bold; }
        .btn:hover { transform: scale(1.05); }
    </style>
</head>
<body>
    <nav>
        <h1>📁 FileMarket</h1>
        <div>
            <a href="/marketplace">🛍️ Marketplace</a>
            <a href="/login">Connexion</a>
            <a href="/register">Inscription</a>
        </div>
    </nav>
    <div class="hero">
        <div>
            <h2>Vendez vos fichiers facilement</h2>
            <p>Gagnez de l'argent en partageant vos fichiers</p>
            <button class="btn" onclick="window.location.href='/register'">Commencer</button>
        </div>
    </div>
</body>
</html>'''

@app.route('/login')
def login_page():
    return '''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Connexion</title>
<style>
    body { font-family: 'Segoe UI'; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center; }
    .card { background: white; padding: 40px; border-radius: 10px; box-shadow: 0 10px 40px rgba(0,0,0,0.2); width: 100%; max-width: 400px; }
    h1 { text-align: center; margin-bottom: 30px; color: #333; }
    .form-group { margin-bottom: 20px; }
    label { display: block; margin-bottom: 8px; color: #555; font-weight: bold; }
    input { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 5px; font-size: 14px; }
    button { width: 100%; padding: 12px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; }
    .link { text-align: center; margin-top: 20px; }
    .link a { color: #667eea; text-decoration: none; }
    .error { color: red; padding: 10px; background: #fadbd8; border-radius: 5px; margin-bottom: 20px; display: none; }
</style>
</head>
<body>
<div class="card">
    <h1>🔐 Connexion</h1>
    <div class="error" id="error"></div>
    <form onsubmit="login(event)">
        <div class="form-group">
            <label>Email</label>
            <input type="email" id="email" required>
        </div>
        <div class="form-group">
            <label>Mot de passe</label>
            <input type="password" id="password" required>
        </div>
        <button type="submit">Se connecter</button>
    </form>
    <div class="link">Pas de compte? <a href="/register">S'inscrire</a></div>
</div>
<script>
    async function login(e) {
        e.preventDefault();
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email: document.getElementById('email').value, password: document.getElementById('password').value})
        });
        const data = await res.json();
        if (res.ok) window.location.href = '/dashboard';
        else document.getElementById('error').textContent = data.error, document.getElementById('error').style.display = 'block';
    }
</script>
</body>
</html>'''

@app.route('/register')
def register_page():
    return '''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Inscription</title>
<style>
    body { font-family: 'Segoe UI'; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center; }
    .card { background: white; padding: 40px; border-radius: 10px; box-shadow: 0 10px 40px rgba(0,0,0,0.2); width: 100%; max-width: 400px; }
    h1 { text-align: center; margin-bottom: 30px; color: #333; }
    .form-group { margin-bottom: 20px; }
    label { display: block; margin-bottom: 8px; color: #555; font-weight: bold; }
    input { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 5px; font-size: 14px; }
    button { width: 100%; padding: 12px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; }
    .link { text-align: center; margin-top: 20px; }
    .link a { color: #667eea; text-decoration: none; }
    .error { color: red; padding: 10px; background: #fadbd8; border-radius: 5px; margin-bottom: 20px; display: none; }
</style>
</head>
<body>
<div class="card">
    <h1>📝 Inscription</h1>
    <div class="error" id="error"></div>
    <form onsubmit="register(event)">
        <div class="form-group">
            <label>Nom d'utilisateur</label>
            <input type="text" id="username" required>
        </div>
        <div class="form-group">
            <label>Email</label>
            <input type="email" id="email" required>
        </div>
        <div class="form-group">
            <label>Mot de passe</label>
            <input type="password" id="password" required>
        </div>
        <button type="submit">S'inscrire</button>
    </form>
    <div class="link">Déjà inscrit? <a href="/login">Se connecter</a></div>
</div>
<script>
    async function register(e) {
        e.preventDefault();
        const res = await fetch('/api/register', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                username: document.getElementById('username').value,
                email: document.getElementById('email').value,
                password: document.getElementById('password').value
            })
        });
        const data = await res.json();
        if (res.ok) { alert('✅ Inscription réussie!'); window.location.href = '/login'; }
        else document.getElementById('error').textContent = data.error, document.getElementById('error').style.display = 'block';
    }
</script>
</body>
</html>'''

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return {'error': 'Not logged in'}, 401
    return '''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Dashboard</title>
<style>
    body { font-family: 'Segoe UI'; background: #f5f5f5; margin: 0; }
    nav { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; }
    .container { max-width: 1200px; margin: 30px auto; padding: 0 20px; }
    .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 30px; }
    .stat-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
    .stat-card h3 { color: #666; margin: 0 0 10px 0; }
    .stat-value { font-size: 32px; font-weight: bold; color: #667eea; }
    .section { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
    .upload-form { display: grid; gap: 15px; }
    input, textarea { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 5px; font-size: 14px; }
    button { padding: 12px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; }
    .files-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 20px; }
    .file-card { background: #f9f9f9; padding: 15px; border-radius: 8px; border: 1px solid #eee; }
</style>
</head>
<body>
<nav><h1>📊 Dashboard</h1></nav>
<div class="container">
    <div class="stats">
        <div class="stat-card"><h3>💰 Solde</h3><div class="stat-value" id="balance">0€</div></div>
        <div class="stat-card"><h3>📁 Fichiers</h3><div class="stat-value" id="files-count">0</div></div>
        <div class="stat-card"><h3>📥 Ventes</h3><div class="stat-value" id="sales-count">0</div></div>
    </div>
    
    <div class="section">
        <h2>📤 Vendre un fichier</h2>
        <form class="upload-form" onsubmit="uploadFile(event)">
            <input type="text" id="filename" placeholder="Titre" required>
            <textarea id="description" placeholder="Description"></textarea>
            <input type="number" id="price" step="0.01" placeholder="Prix (€)" required>
            <input type="file" id="file" required>
            <button type="submit">📤 Mettre en vente</button>
        </form>
    </div>
    
    <div class="section">
        <h2>📁 Mes fichiers</h2>
        <div class="files-grid" id="my-files"></div>
    </div>
</div>
<script>
    loadDashboard();
    async function loadDashboard() {
        const res = await fetch('/api/dashboard');
        const data = await res.json();
        document.getElementById('balance').textContent = data.balance.toFixed(2) + '€';
        document.getElementById('files-count').textContent = data.files_count;
        document.getElementById('sales-count').textContent = data.sales_count;
        document.getElementById('my-files').innerHTML = data.files.map(f => 
            '<div class="file-card"><h3>' + f.filename + '</h3><p>💰 ' + f.price + '€</p><p>📥 ' + f.downloads + ' téléchargements</p></div>'
        ).join('');
    }
    async function uploadFile(e) {
        e.preventDefault();
        const formData = new FormData();
        formData.append('file', document.getElementById('file').files[0]);
        formData.append('filename', document.getElementById('filename').value);
        formData.append('price', document.getElementById('price').value);
        formData.append('description', document.getElementById('description').value);
        const res = await fetch('/api/upload', { method: 'POST', body: formData });
        if (res.ok) { alert('✅ Fichier uploadé!'); loadDashboard(); document.querySelector('.upload-form').reset(); }
    }
</script>
</body>
</html>'''

@app.route('/marketplace')
def marketplace():
    return '''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Marketplace</title>
<style>
    body { font-family: 'Segoe UI'; background: #f5f5f5; margin: 0; }
    nav { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; }
    .container { max-width: 1200px; margin: 30px auto; padding: 0 20px; }
    .search { margin-bottom: 30px; display: flex; gap: 10px; }
    input { flex: 1; padding: 12px; border: 1px solid #ddd; border-radius: 5px; font-size: 14px; }
    .files-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 20px; }
    .file-card { background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); cursor: pointer; transition: transform 0.3s; }
    .file-card:hover { transform: translateY(-5px); }
    .file-header { padding: 15px; display: flex; justify-content: space-between; }
    .file-header h3 { margin: 0; }
    .price { background: #667eea; color: white; padding: 5px 10px; border-radius: 20px; font-weight: bold; }
    .file-info { padding: 0 15px; font-size: 12px; color: #999; }
    .file-card button { width: calc(100% - 30px); margin: 15px; padding: 10px; background: #667eea; color: white; border: none; border-radius: 5px; cursor: pointer; }
</style>
</head>
<body>
<nav><h1>🏪 Marketplace</h1></nav>
<div class="container">
    <div class="search">
        <input type="text" id="search" placeholder="🔍 Rechercher..." onkeyup="searchFiles()">
    </div>
    <div class="files-grid" id="files"></div>
</div>
<script>
    loadFiles();
    async function loadFiles() {
        const search = document.getElementById('search').value;
        const res = await fetch('/api/files?search=' + search);
        const data = await res.json();
        document.getElementById('files').innerHTML = data.files.map(f => 
            '<div class="file-card"><div class="file-header"><h3>' + f.filename + '</h3><span class="price">' + f.price + '€</span></div>' +
            '<p class="file-info">📥 ' + f.downloads + ' téléchargements</p>' +
            '<p class="file-info">Par: ' + f.owner + '</p>' +
            '<button onclick="window.location.href=\\'/file/' + f.id + '\\'">Voir</button></div>'
        ).join('');
    }
    function searchFiles() { loadFiles(); }
</script>
</body>
</html>'''

@app.route('/file/<int:file_id>')
def file_detail(file_id):
    return f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Fichier</title>
<style>
    body {{ font-family: 'Segoe UI'; background: #f5f5f5; margin: 0; }}
    nav {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; }}
    .container {{ max-width: 800px; margin: 30px auto; padding: 0 20px; }}
    .detail {{ background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
    h1 {{ margin: 0 0 20px 0; }}
    .info {{ display: flex; gap: 20px; margin-bottom: 20px; padding: 15px; background: #f5f5f5; border-radius: 5px; }}
    .price {{ font-size: 32px; font-weight: bold; color: #667eea; }}
    button {{ padding: 12px 24px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; font-size: 16px; }}
</style>
</head>
<body>
<nav><h1>📁 Fichier</h1></nav>
<div class="container">
    <div class="detail" id="detail"></div>
</div>
<script>
    async function loadFile() {{
        const res = await fetch('/api/files/{file_id}');
        const f = await res.json();
        document.getElementById('detail').innerHTML = 
            '<h1>' + f.filename + '</h1>' +
            '<div class="info">' +
            '<div><strong>📦 Taille:</strong> ' + (f.file_size / (1024*1024)).toFixed(2) + ' MB</div>' +
            '<div><strong>📥 Téléchargements:</strong> ' + f.downloads + '</div>' +
            '</div>' +
            '<p>' + f.description + '</p>' +
            '<div style="margin: 30px 0;">' +
            '<span class="price">' + f.price + '€</span>' +
            '<button onclick="buyFile({file_id})">🛒 Acheter</button>' +
            '</div>';
    }}
    loadFile();
    function buyFile(id) {{ alert('Achat: implémentation Stripe'); }}
</script>
</body>
</html>'''

# ========== API ROUTES ==========

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.json
    if User.query.filter_by(email=data['email']).first():
        return {'error': 'Email déjà utilisé'}, 400
    user = User(email=data['email'], username=data['username'])
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    session['user_id'] = user.id
    return {'message': 'OK', 'user_id': user.id}, 201

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    user = User.query.filter_by(email=data['email']).first()
    if not user or not user.check_password(data['password']):
        return {'error': 'Identifiants incorrects'}, 401
    session['user_id'] = user.id
    return {'message': 'OK', 'user_id': user.id}, 200

@app.route('/api/upload', methods=['POST'])
def api_upload():
    if 'user_id' not in session:
        return {'error': 'Not logged in'}, 401
    
    file = request.files['file']
    filename = secure_filename(file.filename)
    s3_key = f"files/{session['user_id']}/{uuid.uuid4()}_{filename}"
    
    try:
        s3.upload_fileobj(file, os.getenv('AWS_S3_BUCKET'), s3_key)
    except:
        return {'error': 'Upload échoué'}, 500
    
    new_file = File(
        owner_id=session['user_id'],
        filename=request.form['filename'],
        s3_key=s3_key,
        file_size=len(file.read()),
        price=float(request.form['price']),
        description=request.form['description']
    )
    db.session.add(new_file)
    db.session.commit()
    return {'message': 'OK', 'file_id': new_file.id}, 201

@app.route('/api/files')
def api_files():
    search = request.args.get('search', '')
    query = File.query
    if search:
        query = query.filter(File.filename.ilike(f'%{search}%'))
    files = query.all()
    return {'files': [{
        'id': f.id,
        'filename': f.filename,
        'price': f.price,
        'description': f.description,
        'downloads': f.downloads,
        'owner': f.owner.username
    } for f in files]}, 200

@app.route('/api/files/<int:file_id>')
def api_file(file_id):
    f = File.query.get(file_id)
    return {
        'id': f.id,
        'filename': f.filename,
        'price': f.price,
        'description': f.description,
        'file_size': f.file_size,
        'downloads': f.downloads,
        'owner': f.owner.username
    }, 200

@app.route('/api/dashboard')
def api_dashboard():
    if 'user_id' not in session:
        return {'error': 'Not logged in'}, 401
    user = User.query.get(session['user_id'])
    files = File.query.filter_by(owner_id=user.id).all()
    return {
        'balance': user.balance,
        'files_count': len(files),
        'sales_count': sum([f.downloads for f in files]),
        'files': [{
            'id': f.id,
            'filename': f.filename,
            'price': f.price,
            'downloads': f.downloads
        } for f in files]
    }, 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
