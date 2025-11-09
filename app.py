import os
import re
import json
import base64
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

from datetime import datetime, timedelta

# --- Ortam değişkenlerini yükle ---
from dotenv import load_dotenv
load_dotenv()

# --- Flask Uygulaması ve Veritabanı Kurulumu ---
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)

# Hassas bilgileri ortam değişkenlerinden al!
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret_key_lutfen_degistirin_cok_uzun_olsun')

# Veritabanı Yapılandırması: Sadece yerel SQLite kullan
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'users_and_passwords.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Bu sayfaya erişmek için giriş yapmalısınız."
login_manager.login_message_category = "danger"

# --- Sabit bir tuz (salt) ---
# APP_SALT'ı ortam değişkeninden alıyoruz. Yoksa varsayılan rastgele bir tane kullanırız.
APP_SALT_ENV = os.getenv('APP_SALT', '').strip()
if APP_SALT_ENV:
    APP_SALT = APP_SALT_ENV.encode('utf-8')
else:
    # Varsayılan salt kullan (uyarı verme, sessizce devam et)
    APP_SALT = b'gL6G4wWp0cTjK5q9VfB2zXyN7eU1sC3a' # Varsayılan salt - production'da .env'de değiştirin


# --- Şifreleme ve Anahtar Türetme Fonksiyonları ---
def generate_derived_key(password: str, salt: bytes):
    if not isinstance(password, str):
        raise TypeError("Password must be a string")
    if not isinstance(salt, bytes):
        raise TypeError("Salt must be bytes")
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode('utf-8')))

def encrypt_data(data: str, key: bytes):
    f = Fernet(key)
    return f.encrypt(data.encode('utf-8')).decode('utf-8')

def decrypt_data(encrypted_data: str, key: bytes):
    f = Fernet(key)
    return f.decrypt(encrypted_data.encode('utf-8')).decode('utf-8')


# --- Güvenlik Soruları Listesi ---
SECURITY_QUESTIONS = [
    # Aile ve Geçmiş
    {"category": "Aile ve Geçmiş", "questions": [
        "Annenizin (veya babanızın) doğduğu şehir neresidir?",
        "En büyük kardeşinizin ikinci adı nedir?",
        "Babanızın mesleği neydi?",
        "Ebeveynleriniz nerede tanıştı?",
        "Annenizin kızlık soyadı nedir?",
    ]},
    # Çocukluk ve Okul Yılları
    {"category": "Çocukluk ve Okul Yılları", "questions": [
        "İlk evcil hayvanınızın adı neydi?",
        "Büyüdüğünüz sokağın adı nedir?",
        "İlkokula başladığınız okulun adı nedir?",
        "En sevdiğiniz çocukluk arkadaşınızın adı neydi?",
        "Çocukluk lakabınız neydi?",
        "İlk öğretmeninizin adı neydi?",
    ]},
    # "İlk"ler ve "En"ler
    {"category": "İlk'ler ve En'ler", "questions": [
        "İlk arabanızın markası ve modeli neydi?",
        "İlk işinizi yaptığınız şirketin adı nedir?",
        "Lise mezuniyetinizde maskotunuz neydi?",
        "En sevdiğiniz spor takımı hangisidir?",
        "En sevdiğiniz filmin adı nedir?",
        "En sevdiğiniz kitabın adı nedir?",
    ]},
]

def get_all_security_questions():
    """Tüm güvenlik sorularını döndür"""
    all_questions = []
    for category in SECURITY_QUESTIONS:
        all_questions.extend(category["questions"])
    return all_questions

def generate_recovery_key():
    """Rastgele bir kurtarma anahtarı oluştur"""
    import secrets
    import string
    # Format: xxxx-xxxx-xxxx-xxxx (16 karakter, 4 grup)
    chars = string.ascii_uppercase + string.digits
    key_parts = []
    for _ in range(4):
        key_parts.append(''.join(secrets.choice(chars) for _ in range(4)))
    return '-'.join(key_parts)

def generate_key_file_content(user_id, username):
    """Key file içeriği oluştur"""
    import secrets
    import string
    # Benzersiz bir key oluştur
    chars = string.ascii_letters + string.digits
    key = ''.join(secrets.choice(chars) for _ in range(64))
    
    content = {
        "user_id": user_id,
        "username": username,
        "key": key,
        "created_at": datetime.now().isoformat(),
        "type": "WSY_RECOVERY_KEY_FILE"
    }
    return json.dumps(content, indent=2), key

# --- Şifre Gücü Kontrolü ---
def check_password_strength(password: str):
    score = 0
    feedback = []

    if len(password) >= 14:
        score += 4
        feedback.append("Şifre uzunluğu mükemmel! (14+ karakter)")
    elif len(password) >= 10:
        score += 3
        feedback.append("Şifre yeterince uzun. Daha uzun olması daha iyi olur (min 10).")
    elif len(password) >= 8:
        score += 2
        feedback.append("Şifre kısa. En az 8, tercihen 14+ karakter olmalı.")
    else:
        feedback.append("Şifre çok kısa. En az 8 karakter olmalı, 14+ önerilir.")

    if re.search(r"[A-Z]", password):
        score += 1
    else:
        feedback.append("Büyük harf (A-Z) ekleyin.")

    if re.search(r"[a-z]", password):
        score += 1
    else:
        feedback.append("Küçük harf (a-z) ekleyin.")

    if re.search(r"\d", password):
        score += 1
    else:
        feedback.append("Sayı (0-9) ekleyin.")

    if re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?`~]", password):
        score += 1
    else:
        feedback.append("Özel karakter (!@#$ vb.) ekleyin.")

    if len(password) > 5 and len(set(list(password))) < len(password) * 0.7:
        feedback.append("Çok fazla tekrar eden karakter veya basit desenler içeriyor. Daha çeşitli yapın.")

    common_words = ["password", "123456", "qwerty", "admin", "yusuf", "sifre", "parola", "12345678", "abcde"]
    if any(word in password.lower() for word in common_words):
        score -= 2
        feedback.append("Ortak veya tahmin edilebilir kelimeler kullanmaktan kaçının.")
    
    if re.search(r"(abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz)", password.lower()):
        score -= 1
        feedback.append("Ardışık karakterler kullanmaktan kaçının (örn. 'abc').")
    if re.search(r"(123|234|345|456|567|678|789|012)", password):
        score -= 1
        feedback.append("Ardışık sayılar kullanmaktan kaçının (örn. '123').")
    if re.search(r"(qwe|wer|ert|rty|tyu|yui|uio|iop|asd|sdf|dfg|fgh|ghj|hjk|jkl|zxc|xcv|cvb|vbn|bnm)", password.lower()):
        score -= 1
        feedback.append("Klavye dizilimi kullanmaktan kaçının (örn. 'qwe').")

    if re.search(r"(cba|edc|fed|gfe|ihg|kji|lkj|pon|rqp|tsr|vut|xwv|zyx)", password.lower()):
        score -= 1
        feedback.append("Tersten ardışık karakterler kullanmaktan kaçının (örn. 'cba').")
    if re.search(r"(321|432|543|654|765|876|987)", password):
        score -= 1
        feedback.append("Tersten ardışık sayılar kullanmaktan kaçının (örn. '321').")
    if re.search(r"(ewq|tre|yrt|iuy|poi|dsa|gfd|jhg|lkj|vbn|mno|xcz)", password.lower()):
        score -= 1
        feedback.append("Tersten klavye dizilimi kullanmaktan kaçının (örn. 'ewq').")

    if score >= 7:
        strength = "Çok Güçlü"
        color = "#4CAF50" # Yeşil
    elif score >= 5:
        strength = "Güçlü"
        color = "#8BC34A" # Açık Yeşil
    elif score >= 3:
        strength = "Orta"
        color = "#FFC107" # Sarı
    else:
        strength = "Zayıf"
        color = "#F44336" # Kırmızı
        
    return strength, color, feedback


# --- Migration Fonksiyonu (Modeller tanımlanmadan önce) ---
def run_migration_early():
    """Veritabanı migration işlemini çalıştır (modeller yüklenmeden önce)"""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        if not os.path.exists(db_path):
            # Veritabanı yoksa, create_all zaten oluşturacak
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # User tablosu var mı kontrol et
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user'")
        if not cursor.fetchone():
            # Tablo yoksa, create_all oluşturacak
            conn.close()
            return
        
        # User tablosu sütunlarını kontrol et
        cursor.execute("PRAGMA table_info(user)")
        user_columns = [col[1] for col in cursor.fetchall()]
        
        # PasswordEntry tablosu var mı kontrol et
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='password_entry'")
        password_entry_exists = cursor.fetchone() is not None
        
        password_entry_columns = []
        if password_entry_exists:
            cursor.execute("PRAGMA table_info(password_entry)")
            password_entry_columns = [col[1] for col in cursor.fetchall()]
        
        migration_needed = False
        
        # last_password_change
        if 'last_password_change' not in user_columns:
            cursor.execute("ALTER TABLE user ADD COLUMN last_password_change DATETIME")
            migration_needed = True
        
        # Şifre sıfırlama sütunları
        if 'security_questions' not in user_columns:
            cursor.execute("ALTER TABLE user ADD COLUMN security_questions TEXT")
            migration_needed = True
        
        if 'recovery_key_hash' not in user_columns:
            cursor.execute("ALTER TABLE user ADD COLUMN recovery_key_hash VARCHAR(128)")
            migration_needed = True
        
        if 'key_file_hash' not in user_columns:
            cursor.execute("ALTER TABLE user ADD COLUMN key_file_hash VARCHAR(128)")
            migration_needed = True
        
        if 'recovery_methods' not in user_columns:
            cursor.execute("ALTER TABLE user ADD COLUMN recovery_methods TEXT")
            cursor.execute("UPDATE user SET recovery_methods = '[]' WHERE recovery_methods IS NULL")
            migration_needed = True
        
        # created_at ve updated_at
        if password_entry_exists:
            if 'created_at' not in password_entry_columns:
                cursor.execute("ALTER TABLE password_entry ADD COLUMN created_at DATETIME")
                cursor.execute("UPDATE password_entry SET created_at = datetime('now') WHERE created_at IS NULL")
                migration_needed = True
            
            if 'updated_at' not in password_entry_columns:
                cursor.execute("ALTER TABLE password_entry ADD COLUMN updated_at DATETIME")
                cursor.execute("UPDATE password_entry SET updated_at = datetime('now') WHERE updated_at IS NULL")
                migration_needed = True
        
        if migration_needed:
            conn.commit()
            print("✅ Veritabanı migration tamamlandı!")
        else:
            print("✓ Veritabanı şeması güncel.")
        
        conn.close()
        
    except sqlite3.OperationalError as e:
        error_msg = str(e).lower()
        if 'duplicate column' in error_msg or 'already exists' in error_msg or 'no such table' in error_msg:
            # Sütun zaten varsa veya tablo yoksa sorun yok
            pass
        else:
            print(f"⚠️ Migration hatası: {e}")
    except Exception as e:
        # Migration hatasını göster ama uygulama çalışmaya devam etsin
        print(f"⚠️ Migration genel hatası: {e}")
        print("   Lütfen migrate_db.bat dosyasını çalıştırın veya migrate_db.py scriptini manuel olarak çalıştırın.")

# Migration'ı hemen çalıştır (modeller yüklenmeden önce)
with app.app_context():
    run_migration_early()

# --- Veritabanı Modelleri ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128)) 
    encrypted_data_encryption_key = db.Column(db.Text, nullable=True) 
    
    email_confirmed = db.Column(db.Boolean, default=False)
    confirmation_code = db.Column(db.String(6), nullable=True) 
    login_attempts = db.Column(db.Integer, default=0)
    lockout_until = db.Column(db.DateTime, nullable=True)
    last_password_change = db.Column(db.DateTime, nullable=True)
    
    # Şifre sıfırlama yöntemleri
    # Güvenlik soruları (JSON formatında: [{"question": "...", "answer_hash": "..."}, ...])
    security_questions = db.Column(db.Text, nullable=True)
    # Recovery key hash
    recovery_key_hash = db.Column(db.String(128), nullable=True)
    # Key file hash
    key_file_hash = db.Column(db.String(128), nullable=True)
    # Aktif kurtarma yöntemleri (JSON: ["security_questions", "recovery_key", "key_file"])
    recovery_methods = db.Column(db.Text, nullable=True, default='[]')

    password_entries = db.relationship('PasswordEntry', backref='user_rel', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_decrypted_data_key(self, master_password: str) -> bytes:
        master_derived_key = generate_derived_key(master_password, APP_SALT)
        try:
            decrypted_key_bytes_str = decrypt_data(self.encrypted_data_encryption_key, master_derived_key)
            return decrypted_key_bytes_str.encode('utf-8')
        except Exception as e:
            print(f"Error decrypting data encryption key: {e}")
            raise ValueError("Ana şifre yanlış veya anahtar bozulmuş.")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class PasswordEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    site = db.Column(db.String(200), nullable=False)
    username = db.Column(db.String(200), nullable=False)
    encrypted_password = db.Column(db.Text, nullable=False) 
    category = db.Column(db.String(100), default="Genel")
    strength = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now) 


# --- Rotalar ---

@app.route('/')
def index():
    if current_user.is_authenticated:
        return render_template('index.html', user=current_user) 
    return render_template('index.html', user=None)

@app.route('/TANITIM.html')
def tanitim():
    """TANITIM.html dosyasını servis eder"""
    return send_from_directory(basedir, 'TANITIM.html')

@app.route('/check_username', methods=['POST'])
def check_username():
    """Kullanıcı adının müsait olup olmadığını kontrol eder (AJAX endpoint)"""
    data = request.get_json()
    username = data.get('username', '').strip()
    
    if not username:
        return jsonify({'available': False, 'message': 'Kullanıcı adı boş olamaz'})
    
    user = User.query.filter_by(username=username).first()
    if user:
        return jsonify({'available': False, 'message': 'Bu kullanıcı adı zaten kullanılıyor'})
    
    return jsonify({'available': True, 'message': 'Kullanıcı adı müsait'})

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password'].strip()

        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            flash('Geçersiz e-posta formatı. Lütfen geçerli bir e-posta adresi girin.', 'danger')
            return redirect(url_for('register'))

        user_by_username = User.query.filter_by(username=username).first()
        if user_by_username:
            flash('Kullanıcı adı zaten mevcut. Lütfen başka bir tane seçin.', 'danger')
            return redirect(url_for('register'))

        # E-posta kontrolünü case-insensitive yap (büyük/küçük harf duyarsız)
        all_users = User.query.all()
        email_lower = email.lower().strip()
        for existing_user in all_users:
            if existing_user.email and existing_user.email.lower().strip() == email_lower:
                flash('Bu e-posta adresi zaten kayıtlı. Lütfen başka bir tane kullanın.', 'danger')
                return redirect(url_for('register'))

        # Kurtarma yöntemlerini kontrol et
        recovery_methods = request.form.getlist('recovery_methods')
        if not recovery_methods:
            flash('En az bir kurtarma yöntemi seçmelisiniz!', 'danger')
            return redirect(url_for('register'))

        try:
            new_user_data_encryption_key = Fernet.generate_key() 
            master_key_for_dek_encryption = generate_derived_key(password, APP_SALT)
            encrypted_dek_for_storage = encrypt_data(new_user_data_encryption_key.decode('utf-8'), master_key_for_dek_encryption)

            new_user = User(username=username, email=email, encrypted_data_encryption_key=encrypted_dek_for_storage)
            new_user.set_password(password)
            new_user.email_confirmed = True
            new_user.recovery_methods = json.dumps(recovery_methods)

            # Güvenlik soruları
            if 'security_questions' in recovery_methods:
                security_questions_data = []
                for i in range(1, 4):  # 3 soru
                    question = request.form.get(f'security_question_{i}', '').strip()
                    answer = request.form.get(f'security_answer_{i}', '').strip()
                    if question and answer:
                        security_questions_data.append({
                            "question": question,
                            "answer_hash": generate_password_hash(answer.lower().strip())
                        })
                
                if len(security_questions_data) != 3:
                    flash('3 güvenlik sorusu ve cevabı girilmelidir!', 'danger')
                    return redirect(url_for('register'))
                
                new_user.security_questions = json.dumps(security_questions_data)

            # Recovery key
            recovery_key = None
            if 'recovery_key' in recovery_methods:
                recovery_key = generate_recovery_key()
                new_user.recovery_key_hash = generate_password_hash(recovery_key)

            # Key file
            key_file_key = None
            key_file_json = None
            if 'key_file' in recovery_methods:
                # Önce kullanıcıyı oluştur, sonra key file oluştur
                db.session.add(new_user)
                db.session.flush()  # ID'yi almak için
                
                key_file_content, key_file_key = generate_key_file_content(new_user.id, username)
                new_user.key_file_hash = generate_password_hash(key_file_key)
                key_file_json = json.loads(key_file_content)
            
            db.session.add(new_user)
            db.session.commit()

            # Key file'ı oluştur ve indirme için hazırla
            key_file_download = None
            if 'key_file' in recovery_methods and key_file_key and key_file_json:
                key_file_download = {
                    'content': key_file_json,  # JSON object olarak gönder
                    'filename': f'WSY_Recovery_Key_{username}_{new_user.id}.json'
                }

            # Recovery key ve key file'ı session'a kaydet (tek seferlik göstermek için)
            session['registration_recovery_key'] = recovery_key
            session['registration_key_file'] = key_file_download

            flash('Kayıt başarıyla tamamlandı! Lütfen kurtarma bilgilerinizi kaydedin.', 'success')
            return redirect(url_for('register_success'))
        except Exception as e:
            db.session.rollback()
            print(f"Kayıt sırasında hata: {e}") 
            flash(f'Kayıt sırasında bir hata oluştu: {e}. Lütfen tekrar deneyin.', 'danger')
            return redirect(url_for('register')) 
    
    security_questions_list = get_all_security_questions()
    return render_template('register.html', user=None, security_questions=security_questions_list, 
                         security_questions_categories=SECURITY_QUESTIONS)

@app.route('/register_success')
def register_success():
    """Kayıt sonrası kurtarma bilgilerini göster"""
    recovery_key = session.get('registration_recovery_key')
    key_file = session.get('registration_key_file')
    
    if not recovery_key and not key_file:
        # Eğer session'da yoksa, zaten gösterilmiş demektir
        flash('Kurtarma bilgileri zaten gösterildi. Giriş yapabilirsiniz.', 'info')
        return redirect(url_for('login'))
    
    # Session'dan temizle (tek seferlik göstermek için)
    session.pop('registration_recovery_key', None)
    session.pop('registration_key_file', None)
    
    return render_template('register_success.html', recovery_key=recovery_key, key_file=key_file)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        user = User.query.filter_by(username=username).first()
        
        # --- Kilitleme Kontrolü Başlangıcı ---
        if user and user.lockout_until and user.lockout_until > datetime.now():
            remaining_time = user.lockout_until - datetime.now()
            hours, remainder = divmod(remaining_time.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            
            flash_msg = "Hesabınız kilitli. "
            if hours > 0:
                flash_msg += f"{int(hours)} saat "
            if minutes > 0:
                flash_msg += f"{int(minutes)} dakika "
            if seconds > 0:
                flash_msg += f"{int(seconds)} saniye "
            flash_msg += "sonra tekrar deneyin."
            
            flash(flash_msg, 'danger')
            return redirect(url_for('login'))
        # --- Kilitleme Kontrolü Sonu ---

        if user and user.check_password(password):
            user.login_attempts = 0
            user.lockout_until = None
            db.session.commit()

            try:
                decrypted_data_key_bytes = user.get_decrypted_data_key(password)
                session['data_encryption_key'] = base64.urlsafe_b64encode(decrypted_data_key_bytes).decode('utf-8')
                
                login_user(user)
                flash('Başarıyla giriş yaptınız!', 'success')
                return redirect(url_for('dashboard'))
            except ValueError as e:
                flash(f'Giriş başarısız: {e}. Lütfen şifrenizi kontrol edin.', 'danger') 
            except Exception as e:
                flash(f'Giriş sırasında beklenmeyen bir hata oluştu: {e}', 'danger')
        else:
            if user: 
                user.login_attempts += 1
                db.session.commit()

                lockout_durations = {
                    3: timedelta(minutes=10),
                    6: timedelta(hours=1),
                    9: timedelta(days=1)
                }
                
                current_attempts_mod_3 = user.login_attempts % 3
                if current_attempts_mod_3 == 0 and user.login_attempts <= 9: 
                    duration = lockout_durations.get(user.login_attempts)
                    if duration:
                        user.lockout_until = datetime.now() + duration
                        db.session.commit()
                        
                        flash_msg = 'Çok fazla yanlış deneme! Hesabınız '
                        if duration.total_seconds() >= 3600 * 24:
                            flash_msg += f"{int(duration.total_seconds() / (3600 * 24))} gün "
                        elif duration.total_seconds() >= 3600:
                            flash_msg += f"{int(duration.total_seconds() / 3600)} saat "
                        else:
                            flash_msg += f"{int(duration.total_seconds() / 60)} dakika "
                        flash_msg += 'kilitlendi.'
                        flash(flash_msg, 'danger')
                        return redirect(url_for('login'))
                
                remaining_in_level = 3 - (current_attempts_mod_3 if current_attempts_mod_3 != 0 else 3)
                if user.login_attempts >= 9: 
                    flash('Kullanıcı adı veya şifre hatalı. Çok fazla yanlış deneme. Hesabınız 1 gün kilitlendi.', 'danger')
                else:
                    flash(f'Kullanıcı adı veya şifre hatalı. Kalan deneme: {remaining_in_level}', 'danger')
            else: 
                flash('Kullanıcı adı veya şifre hatalı.', 'danger')
    return render_template('login.html', user=None) 

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('data_encryption_key', None) 
    flash('Başarıyla çıkış yaptınız.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    data_encryption_key_b64_str = session.get('data_encryption_key')
    if not data_encryption_key_b64_str:
        flash('Güvenlik nedeniyle tekrar giriş yapmanız gerekiyor.', 'danger')
        return redirect(url_for('login'))

    try:
        encryption_key = base64.urlsafe_b64decode(data_encryption_key_b64_str.encode('utf-8'))
    except Exception as e:
        flash(f'Oturum anahtarı hatası: {e}. Lütfen tekrar giriş yapın.', 'danger')
        return redirect(url_for('logout')) 

    user_passwords = db.session.query(PasswordEntry).filter_by(user_id=current_user.id).all()
    
    decrypted_passwords = []
    for pwd_entry in user_passwords:
        try:
            decrypted_password = decrypt_data(pwd_entry.encrypted_password, encryption_key)
            decrypted_passwords.append({
                'id': pwd_entry.id,
                'site': pwd_entry.site,
                'username': pwd_entry.username,
                'password': decrypted_password,
                'category': pwd_entry.category,
                'strength': pwd_entry.strength 
            })
        except Exception as e:
            print(f"Hata: Şifre çözülürken problem oluştu ID {pwd_entry.id}: {e}")
            decrypted_passwords.append({
                'id': pwd_entry.id,
                'site': pwd_entry.site,
                'username': pwd_entry.username,
                'password': "[Şifre çözülemedi]", 
                'category': pwd_entry.category,
                'strength': "Bilinmiyor"
            })
    
    all_categories_db = db.session.query(PasswordEntry.category).filter_by(user_id=current_user.id).distinct().all()
    categories_list = sorted([cat[0] for cat in all_categories_db])
    if "Genel" not in categories_list:
        categories_list.insert(0, "Genel") 
    
    # İstatistikler
    stats = {
        'total_passwords': len(decrypted_passwords),
        'total_categories': len(categories_list),
        'weak_passwords': len([p for p in decrypted_passwords if p.get('strength') == 'Zayıf']),
        'strong_passwords': len([p for p in decrypted_passwords if p.get('strength') in ['Güçlü', 'Çok Güçlü']]),
        'category_counts': {}
    }
    
    # Kategori sayıları
    for category in categories_list:
        stats['category_counts'][category] = len([p for p in decrypted_passwords if p.get('category') == category])

    return render_template('dashboard.html', user=current_user, passwords=decrypted_passwords, categories=categories_list, stats=stats)


@app.route('/add_password', methods=['GET', 'POST'])
@login_required
def add_password():
    data_encryption_key_b64_str = session.get('data_encryption_key')
    if not data_encryption_key_b64_str:
        flash('Şifre eklemek için tekrar giriş yapmanız gerekiyor.', 'danger')
        return redirect(url_for('login'))

    try:
        encryption_key = base64.urlsafe_b64decode(data_encryption_key_b64_str.encode('utf-8'))
    except Exception as e:
        flash(f'Oturum anahtarı hatası: {e}. Lütfen tekrar giriş yapın.', 'danger')
        return redirect(url_for('logout'))

    all_categories_db = db.session.query(PasswordEntry.category).filter_by(user_id=current_user.id).distinct().all()
    categories_list = sorted([cat[0] for cat in all_categories_db])
    if "Genel" not in categories_list:
        categories_list.insert(0, "Genel")

    if request.method == 'POST':
        site = request.form['site'].strip()
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        category = request.form.get('category', 'Genel').strip()
        strength_text_from_js = request.form.get('strength-text-add') 

        if not site or not username or not password:
            flash('Site, Kullanıcı Adı ve Şifre alanları boş bırakılamaz.', 'danger')
            return redirect(url_for('add_password'))
        if not category:
            category = "Genel"
        
        try:
            encrypted_password = encrypt_data(password, encryption_key)
        except Exception as e:
            flash(f'Şifre şifrelenirken hata oluştu: {e}', 'danger')
            return redirect(url_for('add_password'))

        new_password_entry = PasswordEntry(
            user_id=current_user.id,
            site=site,
            username=username,
            encrypted_password=encrypted_password,
            category=category,
            strength=strength_text_from_js 
        )
        db.session.add(new_password_entry)
        db.session.commit()
        flash('Şifre başarıyla eklendi!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('add_password.html', user=current_user, categories=categories_list)

@app.route('/update_password/<int:password_id>', methods=['GET', 'POST'])
@login_required
def update_password(password_id):
    data_encryption_key_b64_str = session.get('data_encryption_key')
    if not data_encryption_key_b64_str:
        flash('Şifreyi güncellemek için tekrar giriş yapmanız gerekiyor.', 'danger')
        return redirect(url_for('login'))

    try:
        encryption_key = base64.urlsafe_b64decode(data_encryption_key_b64_str.encode('utf-8'))
    except Exception as e:
        flash(f'Oturum anahtarı hatası: {e}. Lütfen tekrar giriş yapın.', 'danger')
        return redirect(url_for('logout'))

    entry_to_update = db.session.query(PasswordEntry).filter_by(id=password_id, user_id=current_user.id).first_or_404()

    try:
        decrypted_pwd = decrypt_data(entry_to_update.encrypted_password, encryption_key)
    except Exception as e:
        flash(f'Şifre çözülürken hata oluştu: {e}. Lütfen tekrar deneyin.', 'danger')
        decrypted_pwd = "[Çözülemedi]" 
    
    all_categories_db = db.session.query(PasswordEntry.category).filter_by(user_id=current_user.id).distinct().all()
    categories_list = sorted([cat[0] for cat in all_categories_db])
    if "Genel" not in categories_list:
        categories_list.insert(0, "Genel")

    if request.method == 'POST':
        entry_to_update.site = request.form['site'].strip()
        entry_to_update.username = request.form['username'].strip()
        new_password_plain = request.form['password'].strip() 
        entry_to_update.category = request.form.get('category', 'Genel').strip()
        strength_text_from_js = request.form.get('strength-text-update') 

        if not entry_to_update.site or not entry_to_update.username or not new_password_plain:
            flash('Tüm alanları doldurmak zorunludur.', 'danger')
            return redirect(url_for('update_password', password_id=password_id))
        
        try:
            encrypted_new_password = encrypt_data(new_password_plain, encryption_key)
            entry_to_update.encrypted_password = encrypted_new_password
            entry_to_update.strength = strength_text_from_js 
        except Exception as e:
            flash(f'Şifre şifrelenirken hata oluştu: {e}', 'danger')
            return redirect(url_for('update_password', password_id=password_id))

        db.session.commit()
        flash('Şifre başarıyla güncellendi!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('update_password.html', user=current_user, entry=entry_to_update, decrypted_pwd=decrypted_pwd, categories=categories_list)


@app.route('/delete_password/<int:password_id>', methods=['POST'])
@login_required
def delete_password(password_id):
    entry_to_delete = db.session.query(PasswordEntry).filter_by(id=password_id, user_id=current_user.id).first_or_404()
    
    db.session.delete(entry_to_delete)
    db.session.commit()
    flash('Şifre başarıyla silindi!', 'info')
    return redirect(url_for('dashboard'))

@app.route('/generate_password', methods=['POST'])
@login_required
def generate_password():
    """Rastgele şifre oluştur"""
    import secrets
    import string
    
    length = int(request.json.get('length', 16))
    include_uppercase = request.json.get('include_uppercase', True)
    include_lowercase = request.json.get('include_lowercase', True)
    include_numbers = request.json.get('include_numbers', True)
    include_symbols = request.json.get('include_symbols', True)
    
    characters = ''
    if include_uppercase:
        characters += string.ascii_uppercase
    if include_lowercase:
        characters += string.ascii_lowercase
    if include_numbers:
        characters += string.digits
    if include_symbols:
        characters += '!@#$%^&*()_+-=[]{}|;:,.<>?'
    
    if not characters:
        return jsonify({'error': 'En az bir karakter seti seçilmelidir.'}), 400
    
    password = ''.join(secrets.choice(characters) for _ in range(length))
    return jsonify({'password': password})

@app.route('/export_passwords', methods=['GET'])
@login_required
def export_passwords():
    """Şifreleri dışa aktar (JSON formatında)"""
    data_encryption_key_b64_str = session.get('data_encryption_key')
    if not data_encryption_key_b64_str:
        flash('Şifreleri dışa aktarmak için tekrar giriş yapmanız gerekiyor.', 'danger')
        return redirect(url_for('login'))
    
    try:
        encryption_key = base64.urlsafe_b64decode(data_encryption_key_b64_str.encode('utf-8'))
    except Exception as e:
        flash(f'Oturum anahtarı hatası: {e}. Lütfen tekrar giriş yapın.', 'danger')
        return redirect(url_for('logout'))
    
    user_passwords = db.session.query(PasswordEntry).filter_by(user_id=current_user.id).all()
    
    export_data = {
        'export_date': datetime.now().isoformat(),
        'username': current_user.username,
        'passwords': []
    }
    
    for pwd_entry in user_passwords:
        try:
            decrypted_password = decrypt_data(pwd_entry.encrypted_password, encryption_key)
            export_data['passwords'].append({
                'site': pwd_entry.site,
                'username': pwd_entry.username,
                'password': decrypted_password,
                'category': pwd_entry.category,
                'strength': pwd_entry.strength
            })
        except Exception as e:
            print(f"Şifre çözülemedi ID {pwd_entry.id}: {e}")
    
    response = Response(
        json.dumps(export_data, indent=2, ensure_ascii=False),
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename=wsy_passwords_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'}
    )
    return response

@app.route('/import_passwords', methods=['POST'])
@login_required
def import_passwords():
    """Şifreleri içe aktar (JSON formatından)"""
    data_encryption_key_b64_str = session.get('data_encryption_key')
    if not data_encryption_key_b64_str:
        flash('Şifreleri içe aktarmak için tekrar giriş yapmanız gerekiyor.', 'danger')
        return redirect(url_for('login'))
    
    try:
        encryption_key = base64.urlsafe_b64decode(data_encryption_key_b64_str.encode('utf-8'))
    except Exception as e:
        flash(f'Oturum anahtarı hatası: {e}. Lütfen tekrar giriş yapın.', 'danger')
        return redirect(url_for('logout'))
    
    if 'file' not in request.files:
        flash('Dosya seçilmedi.', 'danger')
        return redirect(url_for('dashboard'))
    
    file = request.files['file']
    if file.filename == '':
        flash('Dosya seçilmedi.', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        import_data = json.load(file)
        imported_count = 0
        skipped_count = 0
        
        for pwd_data in import_data.get('passwords', []):
            site = pwd_data.get('site', '').strip()
            username = pwd_data.get('username', '').strip()
            password = pwd_data.get('password', '').strip()
            category = pwd_data.get('category', 'Genel').strip()
            
            if not site or not username or not password:
                skipped_count += 1
                continue
            
            # Aynı site ve kullanıcı adına sahip şifre var mı kontrol et
            existing = PasswordEntry.query.filter_by(
                user_id=current_user.id,
                site=site,
                username=username
            ).first()
            
            if existing:
                skipped_count += 1
                continue
            
            try:
                encrypted_password = encrypt_data(password, encryption_key)
                strength_text, _, _ = check_password_strength(password)
                
                new_entry = PasswordEntry(
                    user_id=current_user.id,
                    site=site,
                    username=username,
                    encrypted_password=encrypted_password,
                    category=category,
                    strength=strength_text
                )
                db.session.add(new_entry)
                imported_count += 1
            except Exception as e:
                print(f"Şifre içe aktarılırken hata: {e}")
                skipped_count += 1
        
        db.session.commit()
        flash(f'{imported_count} şifre başarıyla içe aktarıldı. {skipped_count} şifre atlandı.', 'success')
        
    except json.JSONDecodeError:
        flash('Geçersiz JSON dosyası.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'İçe aktarma sırasında hata oluştu: {e}', 'danger')
    
    return redirect(url_for('dashboard'))

# --- Şifremi Unuttum Rotası ---
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        
        # Kullanıcıyı bul
        user = None
        if username:
            user = User.query.filter_by(username=username).first()
        elif email:
            # E-posta ile arama (case-insensitive)
            all_users = User.query.all()
            email_lower = email.lower().strip()
            for u in all_users:
                if u.email and u.email.lower().strip() == email_lower:
                    user = u
                    break

        if not user:
            flash('Kullanıcı bulunamadı. Lütfen kullanıcı adınızı veya e-posta adresinizi kontrol edin.', 'danger')
            return redirect(url_for('forgot_password'))
        
        # Kullanıcının kurtarma yöntemlerini kontrol et
        recovery_methods = json.loads(user.recovery_methods or '[]')
        if not recovery_methods:
            flash('Bu hesap için kurtarma yöntemi tanımlanmamış. Hesabınıza erişemezsiniz.', 'danger')
            return redirect(url_for('login'))
        
        # Kullanıcıyı session'a kaydet (güvenlik için)
        session['reset_user_id'] = user.id
        session['reset_username'] = user.username
        
        return redirect(url_for('reset_password_method'))
    
    return render_template('forgot_password.html', user=None)

@app.route('/reset_password_method', methods=['GET', 'POST'])
def reset_password_method():
    """Kurtarma yöntemi seçimi"""
    user_id = session.get('reset_user_id')
    if not user_id:
        flash('Geçersiz işlem. Lütfen şifre sıfırlama işlemini baştan başlatın.', 'danger')
        return redirect(url_for('forgot_password'))
    
    user = User.query.get(user_id)
    if not user:
        flash('Kullanıcı bulunamadı.', 'danger')
        session.pop('reset_user_id', None)
        session.pop('reset_username', None)
        return redirect(url_for('forgot_password'))
    
    recovery_methods = json.loads(user.recovery_methods or '[]')
    
    if request.method == 'POST':
        method = request.form.get('method')
        if method not in recovery_methods:
            flash('Geçersiz kurtarma yöntemi!', 'danger')
            return redirect(url_for('reset_password_method'))
        
        session['reset_method'] = method
        return redirect(url_for('reset_password_verify'))
    
    return render_template('reset_password_method.html', user=user, recovery_methods=recovery_methods)

@app.route('/reset_password_verify', methods=['GET', 'POST'])
def reset_password_verify():
    """Kurtarma yöntemi doğrulama"""
    user_id = session.get('reset_user_id')
    method = session.get('reset_method')
    
    if not user_id or not method:
        flash('Geçersiz işlem. Lütfen şifre sıfırlama işlemini baştan başlatın.', 'danger')
        return redirect(url_for('forgot_password'))
    
    user = User.query.get(user_id)
    if not user:
        flash('Kullanıcı bulunamadı.', 'danger')
        session.pop('reset_user_id', None)
        session.pop('reset_username', None)
        session.pop('reset_method', None)
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        verified = False
        
        if method == 'security_questions':
            # 3 güvenlik sorusunu kontrol et
            security_questions = json.loads(user.security_questions or '[]')
            if len(security_questions) != 3:
                flash('Güvenlik soruları bulunamadı.', 'danger')
                return redirect(url_for('forgot_password'))
            
            all_correct = True
            for i, sq in enumerate(security_questions, 1):
                answer = request.form.get(f'answer_{i}', '').strip().lower()
                if not check_password_hash(sq['answer_hash'], answer):
                    all_correct = False
                    break
            
            if all_correct:
                verified = True
            else:
                flash('Güvenlik sorularından biri veya daha fazlası yanlış!', 'danger')
                return render_template('reset_password_verify.html', user=user, method=method, 
                                     security_questions=security_questions)
        
        elif method == 'recovery_key':
            # Recovery key kontrolü
            recovery_key = request.form.get('recovery_key', '').strip().upper()
            if user.recovery_key_hash and check_password_hash(user.recovery_key_hash, recovery_key):
                verified = True
            else:
                flash('Kurtarma anahtarı yanlış!', 'danger')
                return render_template('reset_password_verify.html', user=user, method=method)
        
        elif method == 'key_file':
            # Key file kontrolü
            if 'key_file' not in request.files:
                flash('Key file yüklenmedi!', 'danger')
                return render_template('reset_password_verify.html', user=user, method=method)
            
            file = request.files['key_file']
            if file.filename == '':
                flash('Key file seçilmedi!', 'danger')
                return render_template('reset_password_verify.html', user=user, method=method)
            
            try:
                file_content = json.loads(file.read().decode('utf-8'))
                file_key = file_content.get('key', '')
                
                if user.key_file_hash and check_password_hash(user.key_file_hash, file_key):
                    verified = True
                else:
                    flash('Key file geçersiz!', 'danger')
                    return render_template('reset_password_verify.html', user=user, method=method)
            except Exception as e:
                flash(f'Key file okunamadı: {e}', 'danger')
                return render_template('reset_password_verify.html', user=user, method=method)
        
        if verified:
            session['reset_verified'] = True
            return redirect(url_for('reset_password_new'))
        else:
            flash('Doğrulama başarısız!', 'danger')
            return redirect(url_for('forgot_password'))
    
    # GET isteği - doğrulama formunu göster
    security_questions = None
    if method == 'security_questions':
        security_questions = json.loads(user.security_questions or '[]')
    
    return render_template('reset_password_verify.html', user=user, method=method, 
                         security_questions=security_questions)

@app.route('/reset_password_new', methods=['GET', 'POST'])
def reset_password_new():
    """Yeni şifre belirleme"""
    user_id = session.get('reset_user_id')
    verified = session.get('reset_verified')
    
    if not user_id or not verified:
        flash('Geçersiz işlem. Lütfen şifre sıfırlama işlemini baştan başlatın.', 'danger')
        return redirect(url_for('forgot_password'))
    
    user = User.query.get(user_id)
    if not user:
        flash('Kullanıcı bulunamadı.', 'danger')
        session.pop('reset_user_id', None)
        session.pop('reset_username', None)
        session.pop('reset_method', None)
        session.pop('reset_verified', None)
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        if not new_password or len(new_password) < 8:
            flash('Yeni şifre en az 8 karakter olmalıdır.', 'danger')
            return render_template('reset_password_new.html', user=user)
        
        if new_password != confirm_password:
            flash('Şifreler uyuşmuyor.', 'danger')
            return render_template('reset_password_new.html', user=user)
        
        try:
            # Eski şifre ile data encryption key'i çöz (bu durumda mümkün değil)
            # Yeni şifre ile yeni bir key oluştur ve tüm şifreleri yeniden şifrele
            # NOT: Bu durumda kullanıcının eski şifreleri kaybolur!
            
            # Yeni data encryption key oluştur
            new_user_data_encryption_key = Fernet.generate_key()
            master_key_for_dek_encryption = generate_derived_key(new_password, APP_SALT)
            encrypted_dek_for_storage = encrypt_data(new_user_data_encryption_key.decode('utf-8'), master_key_for_dek_encryption)
            
            # Kullanıcı şifresini güncelle
            user.set_password(new_password)
            user.encrypted_data_encryption_key = encrypted_dek_for_storage
            user.last_password_change = datetime.now()
            
            # NOT: Eski şifreler şifrelenemez, bu yüzden silinir veya uyarı verilir
            # Bu durumda tüm şifreleri sil
            PasswordEntry.query.filter_by(user_id=user.id).delete()
            
            db.session.commit()
            
            # Session'ı temizle
            session.pop('reset_user_id', None)
            session.pop('reset_username', None)
            session.pop('reset_method', None)
            session.pop('reset_verified', None)
            
            flash('Şifreniz başarıyla sıfırlandı! Ancak eski şifreleriniz güvenlik nedeniyle silindi. Lütfen yeni şifreler ekleyin.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Şifre sıfırlanırken hata oluştu: {e}', 'danger')
            return render_template('reset_password_new.html', user=user)
    
    return render_template('reset_password_new.html', user=user)

# --- Şifre Sıfırlama Rotası ---
@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Kullanıcı şifre değiştirme"""
    if request.method == 'POST':
        current_password = request.form.get('current_password', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        # Mevcut şifre kontrolü
        if not current_user.check_password(current_password):
            flash('Mevcut şifreniz yanlış. Lütfen tekrar deneyin.', 'danger')
            return render_template('change_password.html', user=current_user)
        
        # Yeni şifre kontrolü
        if not new_password or len(new_password) < 8:
            flash('Yeni şifre en az 8 karakter olmalıdır.', 'danger')
            return render_template('change_password.html', user=current_user)
        
        if new_password != confirm_password:
            flash('Yeni şifreler uyuşmuyor.', 'danger')
            return render_template('change_password.html', user=current_user)
        
        # Aynı şifre kontrolü
        if current_user.check_password(new_password):
            flash('Yeni şifre mevcut şifrenizle aynı olamaz.', 'danger')
            return render_template('change_password.html', user=current_user)
        
        try:
            # Kullanıcı şifresini güncelle
            current_user.set_password(new_password)
            
            # Data encryption key'i yeni şifre ile yeniden şifrele
            old_master_key = generate_derived_key(current_password, APP_SALT)
            new_master_key = generate_derived_key(new_password, APP_SALT)
            
            # Eski anahtarı çöz
            try:
                old_decrypted_key = decrypt_data(current_user.encrypted_data_encryption_key, old_master_key)
            except Exception as e:
                flash('Mevcut şifre doğru görünüyor ancak şifreleme anahtarı çözülemiyor. Lütfen yönetici ile iletişime geçin.', 'danger')
                return render_template('change_password.html', user=current_user)
            
            # Yeni anahtarla şifrele
            new_encrypted_key = encrypt_data(old_decrypted_key, new_master_key)
            current_user.encrypted_data_encryption_key = new_encrypted_key
            current_user.last_password_change = datetime.now()
            
            db.session.commit()
            
            # Oturumu güncelle
            session['data_encryption_key'] = base64.urlsafe_b64encode(old_decrypted_key.encode('utf-8')).decode('utf-8')
            
            flash('Şifreniz başarıyla değiştirildi!', 'success')
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Şifre değiştirilirken bir hata oluştu: {e}', 'danger')
            return render_template('change_password.html', user=current_user)
    
    return render_template('change_password.html', user=current_user)


if __name__ == '__main__':
    # Tabloları oluştur (yeni tablolar için)
    # Not: run_migration_early() zaten modeller tanımlanmadan önce çalıştı (satır 299-300)
    with app.app_context():
        db.create_all()
    
    app.run(debug=True)