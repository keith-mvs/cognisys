# Test multiple document formats
$testFiles = @(
    "C:\Users\kjfle\00_Inbox\To_Review\2025-05-06_review_text_document.txt",
    "C:\Users\kjfle\00_Inbox\To_Review\Doc1.docx",
    "C:\Users\kjfle\00_Inbox\To_Review\Book1.xlsx"
)

foreach ($file in $testFiles) {
    if (-not (Test-Path $file)) {
        Write-Host "Skipping (not found): $file" -ForegroundColor Gray
        continue
    }

    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "Processing: $(Split-Path -Leaf $file)" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Cyan

    $body = @{
        file_path = $file
    } | ConvertTo-Json

    try {
        $response = Invoke-RestMethod `
            -Uri "http://127.0.0.1:5000/process/document" `
            -Method Post `
            -Body $body `
            -ContentType "application/json" `
            -TimeoutSec 120

        Write-Host "[SUCCESS] Document ID: $($response.document_id)" -ForegroundColor Green

        if ($response.extraction) {
            Write-Host "  Extraction: $($response.extraction.method)" -ForegroundColor Gray
            Write-Host "  Text Length: $($response.extraction.text.Length) chars" -ForegroundColor Gray

            if ($response.extraction.text.Length -gt 100) {
                Write-Host "  Preview: $($response.extraction.text.Substring(0, 100))..." -ForegroundColor Gray
            } else {
                Write-Host "  Content: $($response.extraction.text)" -ForegroundColor Gray
            }
        }

        if ($response.analysis) {
            Write-Host "  Document Type: $($response.analysis.document_type)" -ForegroundColor Gray
            Write-Host "  Entities: $($response.analysis.entities.Count)" -ForegroundColor Gray
        }

    } catch {
        Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host "`n========================================`n" -ForegroundColor Cyan
