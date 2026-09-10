@echo off
cd /d %~dp0..\backend
call .venv\Scripts\activate
python -c "import requests; print(requests.post('http://127.0.0.1:8000/api/seed').json())"
pause
