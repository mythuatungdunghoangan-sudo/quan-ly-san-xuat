@echo off
chcp 65001 >nul
echo.
echo  ==============================================
echo   Quan Ly San Xuat - Cai dat lan dau
echo  ==============================================
echo.
echo  Script nay se:
echo    1. Kiem tra / cai Python tu dong
echo    2. Cai cac thu vien can thiet
echo.
echo  Can ket noi internet. Thoi gian: 2-5 phut.
echo.
pause

REM ---- Tim Python co san ----
set PY=
for %%C in (python py python3) do (
    if not defined PY (
        %%C --version >nul 2>&1
        if not errorlevel 1 set PY=%%C
    )
)

REM Tim trong cac duong dan pho bien (khi Python da cai nhung chua co trong PATH)
if not defined PY (
    for %%D in (
        "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
        "C:\Python314\python.exe"
        "C:\Python313\python.exe"
        "C:\Python312\python.exe"
        "C:\Python311\python.exe"
    ) do (
        if not defined PY (
            if exist %%D set PY=%%D
        )
    )
)

if defined PY (
    echo  [OK] Tim thay Python: %PY%
    goto :install_packages
)

REM ---- Tai va cai Python 3.11 ----
echo  [!] Chua co Python. Dang tai Python 3.11 ...
echo      (file ~27MB, vui long cho)
echo.

set PY_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
set PY_INST=%TEMP%\python_3119_setup.exe

powershell -Command "Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%PY_INST%' -UseBasicParsing"
if not exist "%PY_INST%" (
    echo.
    echo  [LOI] Khong tai duoc Python. Kiem tra lai ket noi internet.
    pause & exit /b 1
)

echo  Dang cai Python 3.11 (co the mat 1-2 phut)...
"%PY_INST%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_launcher=1
if errorlevel 1 (
    echo  [LOI] Cai Python that bai. Thu chay file setup tay.
    start "" "%PY_INST%"
    pause & exit /b 1
)

set PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
if not exist "%PY%" (
    echo  [LOI] Khong tim thay Python sau khi cai. Thu khoi dong lai may va chay lai.
    pause & exit /b 1
)
echo  [OK] Da cai Python 3.11.

:install_packages
echo.
echo  Dang cai cac thu vien (co the mat 2-5 phut lan dau)...
echo.

"%PY%" -m pip install --upgrade pip --quiet
"%PY%" -m pip install -r "%~dp0requirements.txt"

if errorlevel 1 (
    echo.
    echo  [LOI] Cai thu vien that bai. Xem thong bao loi o tren.
    pause & exit /b 1
)

echo.
echo  ==============================================
echo   CAI DAT HOAN TAT!
echo.
echo   Dong cua so nay, sau do chay:
echo     run.bat   de mo ung dung
echo  ==============================================
echo.
pause
