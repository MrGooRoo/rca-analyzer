cd C:\Users\Mr_GooRoo\rca-analyzer

# Применяем патч
git apply --ignore-whitespace p14-progress-bar.patch

# Проверки
ruff check
python -m pytest tests/ -q
npm --prefix frontend run build

# Коммит
git add backend/main.py backend/analyzer.py backend/llm_client.py frontend/src/App.jsx frontend/src/App.css frontend/src/components/ProgressBar.jsx
git commit -m "feat: п.14 — прогресс-бар для single-анализа с real-time обновлением"
git push

Write-Host "✅ Патч п.14 применён успешно!" -ForegroundColor Green