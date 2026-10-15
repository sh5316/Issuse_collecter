@echo off
REM 해외 경제 뉴스 앱 실행
cd /d "%~dp0"
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -m streamlit run newsapp.py
) else (
    echo [안내] .venv 가 없습니다. 먼저 아래 명령으로 환경을 만드세요:
    echo     python -m venv .venv
    echo     .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
)
