# IFMOS ML Complete Workflow
# Master script for the entire ML training and deployment workflow

param(
    [ValidateSet("Setup", "Process", "Collect", "Train", "Complete", "Status")]
    [string]$Stage = "Status"
)

$ErrorActionPreference = "Stop"

Write-Host "`n" -NoNewline
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "    IFMOS ML Workflow Manager" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

function Show-Status {
    Import-Module C:\Users\kjfle\Projects\intelligent-file-management-system\IFMOS-ML-Bridge.psm1

    Write-Host "[*] Checking system status...`n" -ForegroundColor Yellow

    # Check server
    $serverRunning = Test-IFMOSMLServer
    if ($serverRunning) {
        Write-Host "[OK] ML Server: Running" -ForegroundColor Green
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:5000/health" -Method Get
        Write-Host "     GPU: $($health.gpu_name)" -ForegroundColor Gray
    } else {
        Write-Host "[!] ML Server: Not Running" -ForegroundColor Red
    }

    # Check stats
    if ($serverRunning) {
        $stats = Get-IFMOSMLStats
        $categories = Get-IFMOSMLCategories

        Write-Host "`n[OK] Database Statistics:" -ForegroundColor Green
        Write-Host "     Total Documents:     $($stats.total_documents)" -ForegroundColor Gray
        Write-Host "     Total Feedback:      $($stats.total_feedback)" -ForegroundColor Gray
        Write-Host "     Active Categories:   $($categories.Count)" -ForegroundColor Gray
        Write-Host "     Training Sessions:   $($stats.training_sessions)" -ForegroundColor Gray

        # Training readiness
        Write-Host "`n[*] Training Readiness:" -ForegroundColor Yellow
        if ($stats.total_feedback -ge 100) {
            Write-Host "     Excellent! $($stats.total_feedback) labeled documents" -ForegroundColor Green
        } elseif ($stats.total_feedback -ge 50) {
            Write-Host "     Good! $($stats.total_feedback) labeled documents (100+ recommended)" -ForegroundColor Yellow
        } elseif ($stats.total_feedback -ge 10) {
            Write-Host "     Minimum met: $($stats.total_feedback) labeled documents (100+ recommended)" -ForegroundColor Yellow
        } else {
            Write-Host "     Insufficient: $($stats.total_feedback) labeled documents (need 10+)" -ForegroundColor Red
        }
    }

    # Check inbox
    $inboxFiles = (Get-ChildItem "C:\Users\kjfle\00_Inbox\To_Review" -File).Count
    Write-Host "`n[OK] Inbox: $inboxFiles files pending" -ForegroundColor Green

    Write-Host ""
}

function Start-Setup {
    Write-Host "Stage 1: Initial Setup" -ForegroundColor Cyan
    Write-Host "=====================`n" -ForegroundColor Cyan

    # Check if server is running
    Import-Module C:\Users\kjfle\Projects\intelligent-file-management-system\IFMOS-ML-Bridge.psm1

    if (-not (Test-IFMOSMLServer)) {
        Write-Host "[*] ML server not running. Please start it:" -ForegroundColor Yellow
        Write-Host "    Start-IFMOSMLServer`n" -ForegroundColor Gray
    } else {
        Write-Host "[OK] ML server is already running`n" -ForegroundColor Green
    }

    # Create categories
    Write-Host "[*] Creating document categories..." -ForegroundColor Yellow
    $existingCats = Get-IFMOSMLCategories

    if ($existingCats.Count -eq 0) {
        & "C:\Users\kjfle\create_categories.ps1"
        Write-Host "[OK] Categories created`n" -ForegroundColor Green
    } else {
        Write-Host "[OK] Categories already exist ($($existingCats.Count) categories)`n" -ForegroundColor Green
    }

    Write-Host "[DONE] Setup complete!`n" -ForegroundColor Green
    Write-Host "Next: Run with -Stage Process`n" -ForegroundColor Cyan
}

function Start-Processing {
    Write-Host "Stage 2: Batch Processing" -ForegroundColor Cyan
    Write-Host "=========================`n" -ForegroundColor Cyan

    Write-Host "[*] Processing all inbox documents..." -ForegroundColor Yellow
    Write-Host "    This will take several minutes...`n" -ForegroundColor Gray

    & "C:\Users\kjfle\batch_process_inbox.ps1"

    Write-Host "`n[DONE] Processing complete!`n" -ForegroundColor Green
    Write-Host "Next: Run with -Stage Collect`n" -ForegroundColor Cyan
}

function Start-Collection {
    Write-Host "Stage 3: Feedback Collection" -ForegroundColor Cyan
    Write-Host "============================`n" -ForegroundColor Cyan

    Write-Host "[*] Starting interactive feedback collection..." -ForegroundColor Yellow
    Write-Host "    Use auto-suggest mode for faster labeling`n" -ForegroundColor Gray

    & "C:\Users\kjfle\collect_feedback.ps1" -AutoSuggest

    Write-Host "`n[DONE] Feedback collection complete!`n" -ForegroundColor Green
    Write-Host "Next: Run with -Stage Train (after 100+ labeled docs)`n" -ForegroundColor Cyan
}

function Start-Training {
    Write-Host "Stage 4: Model Training" -ForegroundColor Cyan
    Write-Host "======================`n" -ForegroundColor Cyan

    # Check readiness
    & "C:\Users\kjfle\train_classifier.ps1" -CheckReadiness

    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n[*] Starting training..." -ForegroundColor Yellow
        & "C:\Users\kjfle\train_classifier.ps1"

        if ($LASTEXITCODE -eq 0) {
            Write-Host "`n[DONE] Training complete!`n" -ForegroundColor Green
            Write-Host "The classifier is now trained and ready for use.`n" -ForegroundColor Cyan
        }
    }
}

function Start-Complete {
    Write-Host "Complete Workflow (All Stages)" -ForegroundColor Cyan
    Write-Host "==============================`n" -ForegroundColor Cyan

    Write-Host "This will run all stages in sequence:" -ForegroundColor Yellow
    Write-Host "  1. Setup (create categories)" -ForegroundColor Gray
    Write-Host "  2. Process (batch process inbox)" -ForegroundColor Gray
    Write-Host "  3. Collect (gather feedback with auto-suggest)" -ForegroundColor Gray
    Write-Host "  4. Train (train classifier)`n" -ForegroundColor Gray

    Read-Host "Press Enter to continue or Ctrl+C to cancel"

    Start-Setup
    Start-Processing
    Start-Collection

    # Check if ready to train
    Import-Module C:\Users\kjfle\Projects\intelligent-file-management-system\IFMOS-ML-Bridge.psm1
    $stats = Get-IFMOSMLStats

    if ($stats.total_feedback -ge 10) {
        Start-Training
    } else {
        Write-Host "`n[SKIP] Not enough labeled data for training yet" -ForegroundColor Yellow
        Write-Host "      Collect more feedback and run: .\ifmos_ml_workflow.ps1 -Stage Train`n" -ForegroundColor Gray
    }

    Write-Host "`n========================================" -ForegroundColor Green
    Write-Host "    Workflow Complete!" -ForegroundColor Green
    Write-Host "========================================`n" -ForegroundColor Green
}

# Main execution
switch ($Stage) {
    "Status" {
        Show-Status
        Write-Host "Available Stages:" -ForegroundColor Cyan
        Write-Host "  Setup    - Create categories and verify server" -ForegroundColor Gray
        Write-Host "  Process  - Batch process all inbox documents" -ForegroundColor Gray
        Write-Host "  Collect  - Collect feedback interactively" -ForegroundColor Gray
        Write-Host "  Train    - Train the classifier model" -ForegroundColor Gray
        Write-Host "  Complete - Run all stages in sequence`n" -ForegroundColor Gray
        Write-Host "Usage: .\ifmos_ml_workflow.ps1 -Stage <StageName>`n" -ForegroundColor Yellow
    }
    "Setup" { Start-Setup }
    "Process" { Start-Processing }
    "Collect" { Start-Collection }
    "Train" { Start-Training }
    "Complete" { Start-Complete }
}
