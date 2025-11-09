"""
Veritabanı Migration Scripti
Bu script, User ve PasswordEntry tablolarına yeni sütunlar ekler.
"""
import sqlite3
import os

# Veritabanı dosyasının yolu
DB_FILE = 'users_and_passwords.db'

if not os.path.exists(DB_FILE):
    print(f"Veritabanı dosyası bulunamadı: {DB_FILE}")
    print("Veritabanı ilk çalıştırmada oluşturulacak.")
    exit(0)

conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# Önce mevcut sütunları kontrol et
cursor.execute("PRAGMA table_info(user)")
user_columns = [col[1] for col in cursor.fetchall()]

cursor.execute("PRAGMA table_info(password_entry)")
password_entry_columns = [col[1] for col in cursor.fetchall()]

try:
    # User tablosuna last_password_change sütunu ekle
    print("User tablosuna last_password_change sütunu ekleniyor...")
    if 'last_password_change' not in user_columns:
        try:
            cursor.execute("ALTER TABLE user ADD COLUMN last_password_change DATETIME")
            print("✓ last_password_change sütunu eklendi.")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("✓ last_password_change sütunu zaten mevcut.")
            else:
                print(f"⚠️ last_password_change eklenirken hata: {e}")
    else:
        print("✓ last_password_change sütunu zaten mevcut.")

    # PasswordEntry tablosuna created_at sütunu ekle
    print("PasswordEntry tablosuna created_at sütunu ekleniyor...")
    if 'created_at' not in password_entry_columns:
        try:
            cursor.execute("ALTER TABLE password_entry ADD COLUMN created_at DATETIME")
            print("✓ created_at sütunu eklendi.")
            
            # Mevcut kayıtlar için varsayılan değer ata
            cursor.execute("UPDATE password_entry SET created_at = datetime('now') WHERE created_at IS NULL")
            print("✓ Mevcut kayıtlara created_at değeri atandı.")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("✓ created_at sütunu zaten mevcut.")
            else:
                print(f"⚠️ created_at eklenirken hata: {e}")
    else:
        print("✓ created_at sütunu zaten mevcut.")

    # PasswordEntry tablosuna updated_at sütunu ekle
    print("PasswordEntry tablosuna updated_at sütunu ekleniyor...")
    if 'updated_at' not in password_entry_columns:
        try:
            cursor.execute("ALTER TABLE password_entry ADD COLUMN updated_at DATETIME")
            print("✓ updated_at sütunu eklendi.")
            
            # Mevcut kayıtlar için varsayılan değer ata
            cursor.execute("UPDATE password_entry SET updated_at = datetime('now') WHERE updated_at IS NULL")
            print("✓ Mevcut kayıtlara updated_at değeri atandı.")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("✓ updated_at sütunu zaten mevcut.")
            else:
                print(f"⚠️ updated_at eklenirken hata: {e}")
    else:
        print("✓ updated_at sütunu zaten mevcut.")

    # User tablosuna şifre sıfırlama sütunları ekle
    print("User tablosuna şifre sıfırlama sütunları ekleniyor...")
    
    # Önce mevcut sütunları kontrol et
    cursor.execute("PRAGMA table_info(user)")
    existing_columns = [col[1] for col in cursor.fetchall()]
    
    if 'security_questions' not in existing_columns:
        try:
            cursor.execute("ALTER TABLE user ADD COLUMN security_questions TEXT")
            print("✓ security_questions sütunu eklendi.")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("✓ security_questions sütunu zaten mevcut.")
            else:
                print(f"⚠️ security_questions eklenirken hata: {e}")
    else:
        print("✓ security_questions sütunu zaten mevcut.")

    if 'recovery_key_hash' not in existing_columns:
        try:
            cursor.execute("ALTER TABLE user ADD COLUMN recovery_key_hash VARCHAR(128)")
            print("✓ recovery_key_hash sütunu eklendi.")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("✓ recovery_key_hash sütunu zaten mevcut.")
            else:
                print(f"⚠️ recovery_key_hash eklenirken hata: {e}")
    else:
        print("✓ recovery_key_hash sütunu zaten mevcut.")

    if 'key_file_hash' not in existing_columns:
        try:
            cursor.execute("ALTER TABLE user ADD COLUMN key_file_hash VARCHAR(128)")
            print("✓ key_file_hash sütunu eklendi.")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("✓ key_file_hash sütunu zaten mevcut.")
            else:
                print(f"⚠️ key_file_hash eklenirken hata: {e}")
    else:
        print("✓ key_file_hash sütunu zaten mevcut.")

    if 'recovery_methods' not in existing_columns:
        try:
            cursor.execute("ALTER TABLE user ADD COLUMN recovery_methods TEXT")
            cursor.execute("UPDATE user SET recovery_methods = '[]' WHERE recovery_methods IS NULL")
            print("✓ recovery_methods sütunu eklendi.")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("✓ recovery_methods sütunu zaten mevcut.")
            else:
                print(f"⚠️ recovery_methods eklenirken hata: {e}")
    else:
        print("✓ recovery_methods sütunu zaten mevcut.")

    conn.commit()
    print("\n✅ Veritabanı migration başarıyla tamamlandı!")
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ Hata oluştu: {e}")
    print("Değişiklikler geri alındı.")
    exit(1)
finally:
    conn.close()

