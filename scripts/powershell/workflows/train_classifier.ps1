# Train IFMOS ML Classifier
# PowerShell wrapper for the Python training script

param(
    [switch]$CheckReadiness  # Check if ready to train without actually training
)

$pythonExe = "C:\Users\kjfle\Projects\intelligent-file-management-system\Python\venv\Scripts\python.exe"
$trainingScript = "C:\Users\kjfle\Projects\intelligent-file-management-system\Python\train_classifier.py"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "IFMOS ML Classifier Training" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

if ($CheckReadiness) {
    Write-Host "[*] Checking training readiness...`n" -ForegroundColor Yellow

    Import-Module C:\Users\kjfle\Projects\intelligent-file-management-system\IFMOS-ML-Bridge.psm1

    $stats = Get-IFMOSMLStats

    Write-Host "Current Statistics:" -ForegroundColor Cyan
    Write-Host "  Total Documents:     $($stats.total_documents)" -ForegroundColor Gray
    Write-Host "  Total Feedback:      $($stats.total_feedback)" -ForegroundColor Gray
    Write-Host "  Active Categories:   $($stats.active_categories)" -ForegroundColor Gray

    if ($stats.total_feedback -ge 10) {
        Write-Host "`n[READY] Minimum requirements met!" -ForegroundColor Green
        Write-Host "  - At least 10 labeled documents" -ForegroundColor Green

        if ($stats.total_feedback -ge 100) {
            Write-Host "  - Excellent: $($stats.total_feedback) labeled documents (100+ recommended)" -ForegroundColor Green
        } elseif ($stats.total_feedback -ge 50) {
            Write-Host "  - Good: $($stats.total_feedback) labeled documents (more is better)" -ForegroundColor Yellow
        } else {
            Write-Host "  - Warning: Only $($stats.total_feedback) labeled documents (100+ recommended for best accuracy)" -ForegroundColor Yellow
        }

        Write-Host "`nReady to train! Run without -CheckReadiness to proceed.`n" -ForegroundColor Cyan
        exit 0
    } else {
        Write-Host "`n[NOT READY] Insufficient training data" -ForegroundColor Red
        Write-Host "  - Need at least 10 labeled documents" -ForegroundColor Red
        Write-Host "  - Currently have: $($stats.total_feedback)" -ForegroundColor Yellow
        Write-Host "  - Recommended: 100+ for good accuracy`n" -ForegroundColor Yellow

        Write-Host "Next steps:" -ForegroundColor Cyan
        Write-Host "  1. Process more documents: .\batch_process_inbox.ps1" -ForegroundColor Gray
        Write-Host "  2. Provide feedback: .\collect_feedback.ps1 -AutoSuggest`n" -ForegroundColor Gray
        exit 1
    }
}

Write-Host "[*] Starting classifier training...`n" -ForegroundColor Yellow
Write-Host "This process will:" -ForegroundColor Gray
Write-Host "  1. Load labeled documents from database" -ForegroundColor Gray
Write-Host "  2. Extract features and analyze content" -ForegroundColor Gray
Write-Host "  3. Train ensemble model (Random Forest + XGBoost + LightGBM)" -ForegroundColor Gray
Write-Host "  4. Evaluate accuracy and save model`n" -ForegroundColor Gray

Write-Host "Training may take 5-15 minutes depending on dataset size...`n" -ForegroundColor Yellow

# Run Python training script
& $pythonExe $trainingScript

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n========================================" -ForegroundColor Green
    Write-Host "Training Completed Successfully!" -ForegroundColor Green
    Write-Host "========================================`n" -ForegroundColor Green

    Write-Host "The trained model is now active and will be used for future predictions." -ForegroundColor Cyan
    Write-Host "`nRecommended next steps:" -ForegroundColor Yellow
    Write-Host "  1. Process new documents to test accuracy" -ForegroundColor Gray
    Write-Host "  2. Continue collecting feedback to improve" -ForegroundColor Gray
    Write-Host "  3. Retrain periodically as more data is collected`n" -ForegroundColor Gray

} else {
    Write-Host "`n========================================" -ForegroundColor Red
    Write-Host "Training Failed" -ForegroundColor Red
    Write-Host "========================================`n" -ForegroundColor Red

    Write-Host "Please review the error messages above and:" -ForegroundColor Yellow
    Write-Host "  1. Ensure you have sufficient labeled data (10+ documents)" -ForegroundColor Gray
    Write-Host "  2. Check that all required dependencies are installed" -ForegroundColor Gray
    Write-Host "  3. Verify the ML server is running`n" -ForegroundColor Gray

    exit 1
}
