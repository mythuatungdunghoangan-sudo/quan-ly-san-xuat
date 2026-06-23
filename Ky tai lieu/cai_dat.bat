@echo off
chcp 65001 >nul
echo.
echo  =========================================
echo   Cai dat - Ky Tai Lieu
echo  =========================================
echo.

cd /d "%~dp0"

:: Tìm Python
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
        if not defined PY if exist %%D set PY=%%D
    )
)
if not defined PY (
    echo  [LOI] Khong tim thay Python!
    echo  Tai Python tai: https://www.python.org/downloads/
    pause & exit /b 1
)

echo  Dang dung: %PY%
echo.

echo  [1/3] Cap nhat pip...
"%PY%" -m pip install --upgrade pip --quiet

echo  [2/3] Cai cac thu vien chinh...
"%PY%" -m pip install ^
    streamlit ^
    numpy ^
    Pillow ^
    PyMuPDF ^
    openpyxl ^
    python-docx ^
    pandas ^
    streamlit-drawable-canvas ^
    pytesseract ^
    requests ^
    docx2pdf ^
    pywin32 ^
    --quiet

echo  [3/3] Kich hoat pywin32...
"%PY%" -m pip install pywin32 --quiet
"%PY%" -c "import win32com.client" >nul 2>&1
if errorlevel 1 (
    for %%P in (
        "%LOCALAPPDATA%\Programs\Python\Python314\Scripts\pywin32_postinstall.py"
        "%LOCALAPPDATA%\Programs\Python\Python313\Scripts\pywin32_postinstall.py"
        "%LOCALAPPDATA%\Programs\Python\Python312\Scripts\pywin32_postinstall.py"
        "%LOCALAPPDATA%\Programs\Python\Python311\Scripts\pywin32_postinstall.py"
        "%LOCALAPPDATA%\Programs\Python\Python310\Scripts\pywin32_postinstall.py"
    ) do (
        if exist %%P "%PY%" %%P -install >nul 2>&1
    )
)

echo.
echo  =========================================
echo   Cai dat xong! Chay Ky tai lieu.bat
echo  =========================================
echo.
pause
