@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

title WSY - Kurulum

echo ========================================
echo    WSY - Web Şifre Yöneticisi Kurulum
echo ========================================
echo.

REM Proje dizinini bul
set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

REM ==========================================
REM 1. Python Kontrolü
REM ==========================================
echo [1/7] Python kontrolü yapılıyor... (15%%) (Python'un yüklü olup olmadığını kontrol eder)
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [HATA] Python yüklü değil!
    echo.
    set /p INSTALL_PYTHON="Python yüklemek istiyor musunuz? (E/H): "
    if /i "!INSTALL_PYTHON!"=="E" (
        echo.
        echo Lütfen Python'u https://www.python.org/downloads/ adresinden indirin ve yükleyin.
        echo Kurulum sırasında "Add Python to PATH" seçeneğini işaretlemeyi unutmayın!
        echo.
        pause
        exit /b 1
    ) else (
        echo Kurulum iptal edildi.
        pause
        exit /b 1
    )
) else (
    for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
    echo [OK] Python bulundu: !PYTHON_VERSION! (100%%)
)
echo.

REM ==========================================
REM 2. Virtual Environment Kontrolü
REM ==========================================
echo [2/7] Virtual environment kontrolü yapılıyor... (30%%) (Proje için izole bir Python ortamı oluşturur)
if exist "venv" (
    echo [BİLGİ] Virtual environment zaten mevcut.
    set /p RECREATE_VENV="Virtual environment'ı yeniden oluşturmak istiyor musunuz? (E/H): "
    if /i "!RECREATE_VENV!"=="E" (
        echo Virtual environment siliniyor... (40%%)
        rmdir /s /q venv 2>nul
        timeout /t 2 /nobreak >nul
        echo Virtual environment oluşturuluyor... (50%%)
        python -m venv venv
        if errorlevel 1 (
            echo [HATA] Virtual environment oluşturulamadı!
            pause
            exit /b 1
        )
        echo [BILGI] Virtual environment dosyaları oluşturuluyor, lütfen bekleyin...
        REM Python.exe dosyasının varlığını kontrol et (aktivasyon dosyasından daha hızlı oluşur)
        set "RETRY_COUNT=0"
        :check_venv_ready
        if exist "venv\Scripts\python.exe" (
            REM Python.exe var, şimdi aktivasyon dosyasını kontrol et
            timeout /t 2 /nobreak >nul
            if exist "venv\Scripts\activate.bat" (
                echo [OK] Virtual environment oluşturuldu. (100%%)
                goto :venv_created
            ) else if exist "venv\Scripts\Activate.ps1" (
                echo [OK] Virtual environment oluşturuldu. (100%%)
                goto :venv_created
            ) else (
                echo [OK] Virtual environment oluşturuldu. (aktivasyon dosyası kontrol edilecek) (100%%)
                goto :venv_created
            )
        ) else (
            set /a RETRY_COUNT+=1
            if !RETRY_COUNT! LSS 10 (
                timeout /t 1 /nobreak >nul
                goto :check_venv_ready
            ) else (
                echo [UYARI] Virtual environment dosyaları henüz tamamen oluşmadı, devam ediliyor...
                goto :venv_created
            )
        )
    ) else (
        echo [OK] Mevcut virtual environment kullanılıyor. (100%%)
        goto :venv_ready
    )
) else (
    echo Virtual environment bulunamadı.
    set /p CREATE_VENV="Virtual environment oluşturulsun mu? (E/H): "
    if /i "!CREATE_VENV!"=="E" (
        echo Virtual environment oluşturuluyor... (50%%)
        python -m venv venv
        if errorlevel 1 (
            echo [HATA] Virtual environment oluşturulamadı!
            pause
            exit /b 1
        )
        echo [BILGI] Virtual environment dosyaları oluşturuluyor, lütfen bekleyin...
        REM Python.exe dosyasının varlığını kontrol et (aktivasyon dosyasından daha hızlı oluşur)
        set "RETRY_COUNT=0"
        :check_venv_ready2
        if exist "venv\Scripts\python.exe" (
            REM Python.exe var, şimdi aktivasyon dosyasını kontrol et
            timeout /t 2 /nobreak >nul
            if exist "venv\Scripts\activate.bat" (
                echo [OK] Virtual environment oluşturuldu. (100%%)
                goto :venv_created
            ) else if exist "venv\Scripts\Activate.ps1" (
                echo [OK] Virtual environment oluşturuldu. (100%%)
                goto :venv_created
            ) else (
                echo [OK] Virtual environment oluşturuldu. (aktivasyon dosyası kontrol edilecek) (100%%)
                goto :venv_created
            )
        ) else (
            set /a RETRY_COUNT+=1
            if !RETRY_COUNT! LSS 10 (
                timeout /t 1 /nobreak >nul
                goto :check_venv_ready2
            ) else (
                echo [UYARI] Virtual environment dosyaları henüz tamamen oluşmadı, devam ediliyor...
                goto :venv_created
            )
        )
    ) else (
        echo Kurulum iptal edildi.
        pause
        exit /b 1
    )
)

:venv_created
:venv_ready
echo.

REM ==========================================
REM 3. Virtual Environment'ı Aktifleştir
REM ==========================================
echo [3/7] Virtual environment aktifleştiriliyor... (45%%) (Oluşturulan ortamı aktif hale getirir)
REM Aktivasyon dosyasını bul (farklı formatları dene)
set "ACTIVATE_FILE="
if exist "venv\Scripts\activate.bat" (
    set "ACTIVATE_FILE=venv\Scripts\activate.bat"
) else if exist "venv\Scripts\Activate.bat" (
    set "ACTIVATE_FILE=venv\Scripts\Activate.bat"
) else (
    REM Aktivasyon dosyası henüz yoksa, bekleyip tekrar dene
    echo [BILGI] Aktivasyon dosyası aranıyor, lütfen bekleyin...
    set "RETRY_COUNT=0"
    :wait_for_activate
    timeout /t 1 /nobreak >nul
    if exist "venv\Scripts\activate.bat" (
        set "ACTIVATE_FILE=venv\Scripts\activate.bat"
    ) else if exist "venv\Scripts\Activate.bat" (
        set "ACTIVATE_FILE=venv\Scripts\Activate.bat"
    ) else (
        set /a RETRY_COUNT+=1
        if !RETRY_COUNT! LSS 10 (
            goto :wait_for_activate
        )
    )
)

REM Aktivasyon dosyası bulundu mu kontrol et
if "!ACTIVATE_FILE!"=="" (
    echo [HATA] Virtual environment aktivasyon dosyası bulunamadı!
    echo [BILGI] Virtual environment düzgün oluşturulmamış olabilir.
    echo [BILGI] Python.exe kontrolü: 
    if exist "venv\Scripts\python.exe" (
        echo [BILGI] Python.exe mevcut, ancak aktivasyon dosyası bulunamadı.
        echo [BILGI] Virtual environment'ı manuel olarak kontrol edin.
    ) else (
        echo [BILGI] Python.exe de bulunamadı. Virtual environment oluşturulamadı.
    )
    echo [BILGI] Lütfen kurulum.bat dosyasını tekrar çalıştırın.
    pause
    exit /b 1
)

call "!ACTIVATE_FILE!"
echo [OK] Virtual environment aktifleştirildi. (100%%)
echo.

REM ==========================================
REM 4. pip Güncelleme
REM ==========================================
echo [4/7] pip güncelleniyor... (50%%) (Python paket yöneticisini günceller)
python -m pip install --upgrade pip >nul 2>&1
if errorlevel 1 (
    echo [UYARI] pip güncellenemedi, devam ediliyor... (100%%)
) else (
    echo [OK] pip güncellendi. (100%%)
)
echo.

REM ==========================================
REM 5. Requirements.txt Kontrolü
REM ==========================================
echo [5/7] Bağımlılık dosyası kontrolü yapılıyor... (55%%) (Gerekli kütüphanelerin listesini kontrol eder)
if not exist "requirements.txt" (
    echo [HATA] requirements.txt dosyası bulunamadı!
    pause
    exit /b 1
)
echo [OK] requirements.txt bulundu. (100%%)
echo.

REM ==========================================
REM 6. Bağımlılıkları Kontrol Et ve Yükle
REM ==========================================
echo [6/7] Bağımlılıklar kontrol ediliyor... (Gerekli Python kütüphanelerinin yüklü olup olmadığını kontrol eder)
echo.

REM Önce mevcut paketleri kontrol et
echo [BILGI] Bağımlılıklar kontrol ediliyor, lütfen bekleyin... (60%%)
pip list > temp_pip_list.txt 2>nul

REM Temel paketleri kontrol et
set MISSING_FOUND=0
for /f "usebackq tokens=1 delims==" %%p in ("requirements.txt") do (
    set LINE=%%p
    set LINE=!LINE: =!
    if not "!LINE!"=="" (
        for /f "tokens=1 delims==" %%q in ("!LINE!") do (
            set PACKAGE=%%q
            findstr /i /c:"!PACKAGE!" temp_pip_list.txt >nul 2>&1
            if errorlevel 1 (
                set MISSING_FOUND=1
                echo   - !PACKAGE! bulunamadı
            )
        )
    )
)

del temp_pip_list.txt >nul 2>&1
echo [BILGI] Kontrol tamamlandı. (70%%)

REM Bağımlılık yükleme kontrolü
if !MISSING_FOUND!==1 (
    echo.
    echo [BİLGİ] Bazı bağımlılıklar eksik görünüyor.
    set /p INSTALL_DEPS="Bağımlılıkları yüklemek istiyor musunuz? (E/H): "
    if /i "!INSTALL_DEPS!"=="E" (
        echo.
        echo [BILGI] Bağımlılıklar yükleniyor, lütfen bekleyin... (80%%)
        echo [BILGI] Bu işlem birkaç dakika sürebilir...
        echo.
        pip install -r requirements.txt
        if errorlevel 1 (
            echo.
            echo [HATA] Bağımlılıklar yüklenirken hata oluştu!
            pause
            exit /b 1
        )
        echo.
        echo [OK] Tüm bağımlılıklar başarıyla yüklendi. (95%%)
        goto :deps_done
    ) else (
        echo.
        echo [UYARI] Bağımlılıklar yüklenmedi. Uygulama çalışmayabilir!
        goto :deps_done
    )
)

REM Tüm bağımlılıklar zaten yüklü
echo.
echo [OK] Tüm bağımlılıklar yüklü görünüyor.
set /p UPDATE_DEPS="Bağımlılıkları güncellemek ister misiniz? (E/H): "
if /i "!UPDATE_DEPS!"=="E" (
    echo.
    echo [BILGI] Bağımlılıklar kontrol ediliyor ve güncelleniyor... (80%%)
    echo [BILGI] Bu işlem birkaç dakika sürebilir...
    echo.
    pip install -r requirements.txt --upgrade
    if errorlevel 1 (
        echo.
        echo [HATA] Bağımlılıklar güncellenirken hata oluştu!
        pause
        exit /b 1
    )
    echo.
    echo [OK] Bağımlılıklar güncellendi. (95%%)
)

:deps_done
echo.

REM ==========================================
REM 7. .env Dosyası Kontrolü
REM ==========================================
echo [7/7] .env dosyası kontrolü... (96%%) (Uygulama yapılandırma dosyasını kontrol eder)
if not exist ".env" (
    echo [BİLGİ] .env dosyası bulunamadı.
    echo [BİLGİ] Yeni bir .env dosyası oluşturuluyor...
    (
        echo # WSY - Web Şifre Yöneticisi Yapılandırması
        echo # Bu dosyayı düzenleyerek güvenlik ayarlarınızı yapabilirsiniz.
        echo.
        echo # Gizli anahtar - Rastgele uzun bir string oluşturun
        echo SECRET_KEY=default_secret_key_lutfen_degistirin_cok_uzun_olsun
        echo.
        echo # Uygulama Salt - Şifreleme için kullanılır
        echo APP_SALT=gL6G4wWp0cTjK5q9VfB2zXyN7eU1sC3a
    ) > .env
    echo [OK] .env dosyası oluşturuldu. (100%%)
) else (
    echo [OK] .env dosyası mevcut. (100%%)
)
echo.

REM ==========================================
REM 8. Veritabanı Kontrolü
REM ==========================================
echo [Ekstra] Veritabanı kontrolü... (Veritabanı dosyasının varlığını kontrol eder)
if not exist "users_and_passwords.db" (
    echo [BİLGİ] Veritabanı dosyası bulunamadı. İlk çalıştırmada oluşturulacak.
) else (
    echo [OK] Veritabanı dosyası mevcut.
)
echo.

REM ==========================================
REM Kurulum Tamamlandı
REM ==========================================
echo.
echo ========================================
echo    Kurulum Tamamlandı! (100%%)
echo ========================================
echo.
echo Yapılacaklar:
echo 1. .env dosyasını düzenleyerek güvenlik ayarlarınızı yapın (isteğe bağlı)
echo 2. WSY.bat dosyasını çalıştırarak uygulamayı başlatın
echo.
echo Uygulamayı başlatmak için:
echo   - Proje klasöründeki WSY.bat dosyasını çift tıklayın
echo   - Tarayıcınızda http://127.0.0.1:5000 adresinde uygulama açılacaktır
echo.
echo İpucu: Masaüstüne kısayol oluşturmak için WSY.bat dosyasına sağ tıklayıp
echo        "Gönder" ^> "Masaüstü (kısayol oluştur)" seçeneğini kullanabilirsiniz.
echo.
pause
