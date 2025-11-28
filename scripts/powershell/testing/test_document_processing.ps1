# Test document processing with IFMOS ML
$testFile = "C:\Users\kjfle\00_Inbox\To_Review\2024-12-29_review_quest_billing.pdf"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Testing Document Processing" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Processing: $testFile" -ForegroundColor Yellow

$body = @{
    file_path = $testFile
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod `
        -Uri "http://127.0.0.1:5000/process/document" `
        -Method Post `
        -Body $body `
        -ContentType "application/json" `
        -TimeoutSec 120

    Write-Host "`n[SUCCESS] Document processed!" -ForegroundColor Green
    Write-Host "`nDocument ID: $($response.document_id)" -ForegroundColor Cyan

    if ($response.extraction) {
        Write-Host "`n--- Extraction Results ---" -ForegroundColor Yellow
        Write-Host "Success: $($response.extraction.success)"
        Write-Host "Method: $($response.extraction.method)"
        Write-Host "Page Count: $($response.extraction.page_count)"
        Write-Host "Text Length: $($response.extraction.text.Length) characters"
        Write-Host "Text Preview: $($response.extraction.text.Substring(0, [Math]::Min(200, $response.extraction.text.Length)))..."
    }

    if ($response.analysis) {
        Write-Host "`n--- Analysis Results ---" -ForegroundColor Yellow
        Write-Host "Document Type: $($response.analysis.document_type)"
        Write-Host "Entities Found: $($response.analysis.entities.Count)"

        if ($response.analysis.entities.Count -gt 0) {
            Write-Host "`nTop Entities:"
            $response.analysis.entities | Select-Object -First 5 | ForEach-Object {
                Write-Host "  - $($_.text) ($($_.label))"
            }
        }

        Write-Host "`nTop Keywords: $($response.analysis.keywords[0..9] -join ', ')"
    }

    if ($response.prediction) {
        Write-Host "`n--- Prediction Results ---" -ForegroundColor Yellow
        Write-Host "Success: $($response.prediction.success)"

        if ($response.prediction.success) {
            Write-Host "Predicted Category: $($response.prediction.predicted_category)"
            Write-Host "Confidence: $([Math]::Round($response.prediction.confidence * 100, 2))%"
        } else {
            Write-Host "Note: $($response.prediction.note)"
        }
    }

    Write-Host "`n========================================`n" -ForegroundColor Cyan

    # Save full response to file for inspection
    $response | ConvertTo-Json -Depth 10 | Out-File -FilePath "C:\Users\kjfle\ml_test_result.json"
    Write-Host "Full results saved to: C:\Users\kjfle\ml_test_result.json" -ForegroundColor Gray

} catch {
    Write-Host "`n[ERROR] Processing failed!" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red

    if ($_.ErrorDetails) {
        Write-Host "Details: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
}
