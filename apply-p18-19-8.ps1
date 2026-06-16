# Патч для п.18, 19, 8
cd C:\Users\Mr_GooRoo\rca-analyzer

# 1. App.jsx - удаляем блок "Форма скрыта" и добавляем уведомление о похожих
$appJsx = Get-Content "frontend/src/App.jsx" -Raw

# Удаляем блок form-hidden-notice
$appJsx = $appJsx -replace '(?s)\s*<p className="form-hidden-notice">.*?</p>\s*', ''

# Добавляем блок similar-incidents-notice после кнопок (найдем </div> после Button)
$insertPoint = '</div>

                <FormRenderer'

$newBlock = '</div>

                {uploadedMetadata?.similarCount > 0 && !analysisResult && !loading && (
                  <div className="similar-incidents-notice">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                      <path d="M8 1.5C4.41 1.5 1.5 4.41 1.5 8C1.5 11.59 4.41 14.5 8 14.5C11.59 14.5 14.5 11.59 14.5 8C14.5 4.41 11.59 1.5 8 1.5ZM8.75 11.25H7.25V7.25H8.75V11.25ZM8.75 5.75H7.25V4.25H8.75V5.75Z" fill="currentColor"/>
                    </svg>
                    <span>
                      В истории найдено <strong>{uploadedMetadata.similarCount} похожих инцидентов</strong>.
                      После завершения анализа они будут показаны в разделе результатов.
                    </span>
                  </div>
                )}

                <FormRenderer'

$appJsx = $appJsx -replace [regex]::Escape($insertPoint), $newBlock

Set-Content "frontend/src/App.jsx" -Value $appJsx -NoNewline -Encoding UTF8

Write-Host "✓ App.jsx обновлён" -ForegroundColor Green

# 2. App.css - обновляем стили
$appCss = Get-Content "frontend/src/App.css" -Raw

# Удаляем .form-hidden-notice
$appCss = $appCss -replace '(?s)/\* ---- Analyze result state ----.*?\.form-hidden-notice \{[^}]+\}\s*', @'
/* ---- Analyze result state ---- */
.analysis-result-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-md);
  background: var(--bg-success);
  border-radius: var(--radius-lg);
  margin-bottom: var(--space-lg);
}

.analysis-result-toolbar__title {
  font-size: var(--text-lg);
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
}

.analysis-result-toolbar__actions {
  display: flex;
  gap: var(--space-sm);
}

.analysis-result-toolbar button + button {
  margin-left: var(--space-sm);
}

.similar-incidents-notice {
  display: flex;
  align-items: flex-start;
  gap: var(--space-sm);
  padding: var(--space-md);
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  margin-bottom: var(--space-lg);
}

.similar-incidents-notice svg {
  flex-shrink: 0;
  margin-top: 2px;
}

'@

# Обновляем стили для similar-incidents (заменяем секцию)
$appCss = $appCss -replace '(?s)/\* ---- Similar incidents in results ---- \*/.*?(?=/\* ---- |$)', @'
/* ---- Результаты анализа ---- */
.analysis-result__method-title {
  font-size: var(--text-2xl);
  font-weight: 600;
  margin: 0 0 var(--space-sm) 0;
  color: var(--text-primary);
}

.analysis-result__method-description {
  color: var(--text-secondary);
  font-size: var(--text-sm);
  margin: 0 0 var(--space-xl) 0;
}

.similar-incidents-in-results {
  background: var(--bg-secondary);
  padding: var(--space-lg);
  border-radius: var(--radius-lg);
  margin-bottom: var(--space-xl);
}

.similar-incidents-in-results__title {
  font-size: var(--text-md);
  font-weight: 500;
  margin: 0 0 var(--space-sm) 0;
  color: var(--text-primary);
}

.similar-incidents-in-results__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.similar-incident-item {
  padding: var(--space-sm) var(--space-md);
  background: var(--bg-card);
  border-left: 3px solid var(--primary);
  border-radius: var(--radius-sm);
}

.similar-incident-item__title {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: var(--space-xs);
}

.similar-incident-item__description {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.4;
}

.analysis-result__section-title {
  font-size: var(--text-xl);
  font-weight: 600;
  margin: 0 0 var(--space-lg) 0;
  color: var(--text-primary);
}

'@

Set-Content "frontend/src/App.css" -Value $appCss -NoNewline -Encoding UTF8

Write-Host "✓ App.css обновлён" -ForegroundColor Green

# 3. AnalysisResult.jsx - упрощаем структуру
$resultJsx = Get-Content "frontend/src/components/AnalysisResult.jsx" -Raw

# Заменяем analysis-result__title на analysis-result__method-title
$resultJsx = $resultJsx -replace 'className="analysis-result__title"', 'className="analysis-result__method-title"'

# Заменяем секцию similar-incidents
$resultJsx = $resultJsx -replace '(?s)<div className="similar-incidents-section">.*?</div>\s*\)\s*\}', @'
<div className="similar-incidents-in-results">
          <h3 className="similar-incidents-in-results__title">
            📋 Похожие инциденты из истории ({result.similar_incidents.length})
          </h3>
          <div className="similar-incidents-in-results__list">
            {result.similar_incidents.map((inc, idx) => (
              <div key={idx} className="similar-incident-item">
                <div className="similar-incident-item__title">
                  {inc.title || 'Инцидент без названия'}
                </div>
                {inc.description && (
                  <p className="similar-incident-item__description">
                    {inc.description}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
'@

# Заменяем блок content
$resultJsx = $resultJsx -replace '(?s)<div className="analysis-result__content">\s*<div className="analysis-result__incident-title">.*?</div>', @'
<h3 className="analysis-result__section-title">Результаты анализа</h3>

      <div className="analysis-result__content">
        {result.incidentTitle && <h4 className="analysis-result__incident-title">{result.incidentTitle}</h4>}
        
'@

Set-Content "frontend/src/components/AnalysisResult.jsx" -Value $resultJsx -NoNewline -Encoding UTF8

Write-Host "✓ AnalysisResult.jsx обновлён" -ForegroundColor Green

Write-Host "`n✅ Все файлы обновлены!" -ForegroundColor Green