@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM Komut penceresi başlığını ayarla
title WSY - Web Şifre Yöneticisi

REM Proje dizinini bul
set "BATCH_DIR=%~dp0"
set "BATCH_FILE=%~f0"

REM Eğer batch dosyası proje dizinindeyse (venv yanında)
if exist "%BATCH_DIR%venv\Scripts\activate.bat" (
    set "PROJECT_DIR=%BATCH_DIR%"
    goto :found_venv
)

REM Eğer batch dosyası masaüstündeyse, proje dizinini ara
REM Önce app.py dosyasını bul (proje kök dizininde olmalı)
for /f "delims=" %%i in ('where /r "%USERPROFILE%" app.py 2^>nul ^| findstr /i "WSY"') do (
    set "FOUND_APP=%%~dpi"
    if exist "!FOUND_APP!venv\Scripts\activate.bat" (
        set "PROJECT_DIR=!FOUND_APP!"
        goto :found_venv
    )
)

REM Alternatif: Desktop'ta WSY klasörü var mı?
set "DESKTOP_WSY=%USERPROFILE%\Desktop\WSY"
if exist "!DESKTOP_WSY!\venv\Scripts\activate.bat" (
    set "PROJECT_DIR=!DESKTOP_WSY!\"
    goto :found_venv
)

REM Alternatif: Documents'ta WSY klasörü var mı?
set "DOCS_WSY=%USERPROFILE%\Documents\WSY"
if exist "!DOCS_WSY!\venv\Scripts\activate.bat" (
    set "PROJECT_DIR=!DOCS_WSY!\"
    goto :found_venv
)

REM Alternatif: Mevcut çalışma dizininde ara
cd /d "%CD%"
if exist "venv\Scripts\activate.bat" (
    set "PROJECT_DIR=%CD%\"
    goto :found_venv
)

REM En son çare: Kullanıcıya sor
echo [HATA] Virtual environment bulunamadı!
echo.
echo WSY proje klasörünü bulamadım. Lütfen aşağıdaki adımlardan birini deneyin:
echo.
echo 1. WSY.bat dosyasını proje klasörüne kopyalayın ve oradan çalıştırın
echo 2. Proje klasörünün yolunu girin:
echo.
set /p PROJECT_DIR="Proje klasörü yolu (örn: C:\Users\Kullanici\Desktop\WSY): "
if "!PROJECT_DIR!"=="" (
    echo Kurulum iptal edildi.
    pause
    exit /b 1
)

REM Yol sonunda \ yoksa ekle
if not "!PROJECT_DIR:~-1!"=="\" set "PROJECT_DIR=!PROJECT_DIR!\"

if not exist "!PROJECT_DIR!venv\Scripts\activate.bat" (
    echo [HATA] Belirtilen dizinde virtual environment bulunamadı: !PROJECT_DIR!
    echo.
    echo Lütfen önce kurulum.bat dosyasını çalıştırın.
    echo.
    pause
    exit /b 1
)

:found_venv
cd /d "!PROJECT_DIR!"

REM Son kontrol
if not exist "!PROJECT_DIR!venv\Scripts\activate.bat" (
    echo [HATA] Virtual environment bulunamadı: !PROJECT_DIR!venv\Scripts\activate.bat
    echo.
    echo Lütfen önce kurulum.bat dosyasını çalıştırın.
    echo Proje dizini: !PROJECT_DIR!
    echo.
    pause
    exit /b 1
)

REM app.py kontrolü
if not exist "!PROJECT_DIR!app.py" (
    echo [HATA] app.py dosyası bulunamadı: !PROJECT_DIR!app.py
    echo.
    echo Bu WSY.bat dosyası yanlış bir konumda olabilir.
    echo Proje dizini: !PROJECT_DIR!
    echo.
    pause
    exit /b 1
)

echo [BILGI] Proje dizini: !PROJECT_DIR!
echo [BILGI] Virtual environment bulundu.
echo [BILGI] Uygulama başlatılıyor...
echo.

REM Sanal ortamı etkinleştir
call "!PROJECT_DIR!venv\Scripts\activate.bat"

REM Uygulamanın başarıyla başlatılmasını beklemek için kısa bir gecikme
timeout /t 1 /nobreak >nul

REM Flask uygulamasını yeni bir terminal penceresinde başlat
start "" "cmd.exe" /k "title WSY - Sunucu & cd /d "!PROJECT_DIR!" & call "!PROJECT_DIR!venv\Scripts\activate.bat" & python "!PROJECT_DIR!app.py""

REM Tarayıcıyı uygulamanın URL'si ile otomatik olarak aç
REM Kullandığınız varsayılan tarayıcıda açılır
timeout /t 3 /nobreak >nul
start http://127.0.0.1:5000/

REM Bu pencereyi kapat, çünkü uygulama diğer pencerede çalışıyor
timeout /t 1 /nobreak >nul
exit
