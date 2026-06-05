@echo off
chcp 65001 >nul
echo.
echo  =========================================
echo   Phan Loai Tu Dong - Khoi dong ung dung
echo  =========================================
echo.

cd /d "%~dp0"
set PYTHONDONTWRITEBYTECODE=1

set PY=
for %%C in (python py python3) do (
    if not defined PY (
        %%C --version >nul 2>&1
        if not errorlevel 1 set PY=%%C
    )
)

if not defined PY (
    for %%D in (
        "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    ) do (
        if not defined PY (
            if exist %%D set PY=%%D
        )
    )
)

if not defined PY (
    echo  [LOI] Khong tim thay Python! Chay cai_dat.bat truoc.
    pause & exit /b 1
)

echo  Dang khoi dong... Mo trinh duyet tai:
echo  http://localhost:8501
echo.
echo  (Bam Ctrl+C de dung)
echo.
"%PY%" -m streamlit run app.py --server.port 8501 --server.headless false
echo.
pause
