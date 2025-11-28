# Interactive Feedback Collection for IFMOS ML Training
# Reviews processed documents and collects user feedback

param(
    [string]$ResultsPath = "C:\Users\kjfle\ml_batch_results",
    [string]$FeedbackPath = "C:\Users\kjfle\ml_feedback.json",
    [switch]$AutoSuggest  # Auto-suggest categories based on filename patterns
)

Import-Module C:\Users\kjfle\Projects\intelligent-file-management-system\IFMOS-ML-Bridge.psm1

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "IFMOS ML Feedback Collection" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Check if batch results exist
if (-not (Test-Path "$ResultsPath\batch_results.json")) {
    Write-Host "[ERROR] No batch results found!" -ForegroundColor Red
    Write-Host "Please run batch processing first:" -ForegroundColor Yellow
    Write-Host "  .\batch_process_inbox.ps1`n" -ForegroundColor Gray
    exit 1
}

# Load batch results
$results = Get-Content "$ResultsPath\batch_results.json" | ConvertFrom-Json

# Load existing feedback if it exists
$existingFeedback = @{}
if (Test-Path $FeedbackPath) {
    $feedback = Get-Content $FeedbackPath | ConvertFrom-Json
    foreach ($item in $feedback) {
        $existingFeedback[$item.document_id] = $item
    }
    Write-Host "Loaded $($existingFeedback.Count) existing feedback entries`n" -ForegroundColor Gray
}

# Get available categories
Write-Host "[*] Loading categories..." -ForegroundColor Yellow
$categories = Get-IFMOSMLCategories
Write-Host "[OK] Found $($categories.Count) categories`n" -ForegroundColor Green

# Display categories
Write-Host "Available Categories:" -ForegroundColor Yellow
for ($i = 0; $i -lt $categories.Count; $i++) {
    Write-Host "  [$($i + 1)] $($categories[$i].category_name) - $($categories[$i].description)" -ForegroundColor Cyan
}
Write-Host ""

# Auto-suggest function based on filename
function Get-SuggestedCategory {
    param($fileName)

    # Pattern matching for auto-suggestion
    $patterns = @{
        "Legal_CCO" = "cco_\d+"
        "Healthcare_Medical" = "quest|billing|medical"
        "Legal_PropertyTax" = "property|tax|code"
        "Real_Estate" = "realty|notes"
        "Education" = "education|childhood|mexico"
        "Technology" = "mozilla|recovery|onedrive|directorystructure"
        "Personal_Letters" = "letter"
        "Personal_Documents" = "temporary|id"
        "Work_Documents" = "text_document|doc\d+|document"
    }

    foreach ($cat in $patterns.Keys) {
        if ($fileName -match $patterns[$cat]) {
            return $cat
        }
    }

    return $null
}

# Statistics
$feedbackStats = @{
    total = $results.Count
    reviewed = 0
    correct = 0
    corrected = 0
    skipped = 0
}

# Review each document
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Beginning Document Review" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan
Write-Host "Commands: [1-$($categories.Count)] = Select category | S = Skip | Q = Quit | A = Auto (batch remaining)`n" -ForegroundColor Gray

foreach ($result in $results) {
    # Skip if already has feedback
    if ($existingFeedback.ContainsKey($result.document_id)) {
        $feedbackStats.skipped++
        continue
    }

    Clear-Host
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "Document Review [$($feedbackStats.reviewed + 1)/$($feedbackStats.total)]" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan

    Write-Host "File: $($result.file_name)" -ForegroundColor Yellow
    Write-Host "Document ID: $($result.document_id)" -ForegroundColor Gray
    Write-Host "Document Type: $($result.document_type)" -ForegroundColor Gray
    Write-Host "Entities Found: $($result.entities_count)" -ForegroundColor Gray
    Write-Host "Text Length: $($result.text_length) chars" -ForegroundColor Gray

    # Show predicted category if available
    if ($result.predicted_category) {
        Write-Host "`nPredicted: $($result.predicted_category) (Confidence: $([Math]::Round($result.confidence * 100, 1))%)" -ForegroundColor Magenta
    }

    # Auto-suggest category
    $suggested = $null
    if ($AutoSuggest) {
        $suggested = Get-SuggestedCategory -fileName $result.file_name
        if ($suggested) {
            $suggestedNum = ($categories | Where-Object { $_.category_name -eq $suggested }).category_id
            Write-Host "Suggested: [$suggestedNum] $suggested" -ForegroundColor Green
        }
    }

    Write-Host "`nAvailable Categories:" -ForegroundColor Yellow
    for ($i = 0; $i -lt $categories.Count; $i++) {
        $marker = if ($suggested -eq $categories[$i].category_name) { " <--" } else { "" }
        Write-Host "  [$($i + 1)] $($categories[$i].category_name)$marker" -ForegroundColor Cyan
    }

    Write-Host "`nSelect category [1-$($categories.Count)], S=Skip, Q=Quit, A=Auto:" -NoNewline -ForegroundColor Yellow
    $choice = Read-Host " "

    # Handle choice
    switch -Regex ($choice) {
        '^[qQ]$' {
            Write-Host "`n[*] Quitting feedback collection..." -ForegroundColor Yellow
            break
        }
        '^[sS]$' {
            Write-Host "[*] Skipped" -ForegroundColor Gray
            $feedbackStats.skipped++
            continue
        }
        '^[aA]$' {
            Write-Host "`n[*] Auto-mode enabled. Processing remaining documents..." -ForegroundColor Cyan
            # Process this and all remaining with auto-suggestions
            $remainingResults = $results[$feedbackStats.reviewed..($results.Count - 1)]
            foreach ($autoResult in $remainingResults) {
                $autoSuggested = Get-SuggestedCategory -fileName $autoResult.file_name
                if ($autoSuggested) {
                    $feedback = @{
                        document_id = $autoResult.document_id
                        correct_category = $autoSuggested
                        was_correct = $false
                        comment = "Auto-categorized based on filename"
                        timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
                        auto_generated = $true
                    }

                    Submit-IFMOSMLFeedback `
                        -DocumentId $autoResult.document_id `
                        -CorrectCategory $autoSuggested `
                        -WasCorrect $false `
                        -Comment "Auto-categorized" | Out-Null

                    $existingFeedback[$autoResult.document_id] = $feedback
                    $feedbackStats.corrected++
                    Write-Host "  [AUTO] $($autoResult.file_name) -> $autoSuggested" -ForegroundColor Gray
                }
                $feedbackStats.reviewed++
            }
            break
        }
        '^\d+$' {
            $catNum = [int]$choice
            if ($catNum -ge 1 -and $catNum -le $categories.Count) {
                $selectedCat = $categories[$catNum - 1].category_name

                # Check if prediction was correct
                $wasCorrect = ($result.predicted_category -eq $selectedCat)

                $feedback = @{
                    document_id = $result.document_id
                    correct_category = $selectedCat
                    was_correct = $wasCorrect
                    comment = "User review"
                    timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
                    auto_generated = $false
                }

                # Submit feedback to ML system
                Write-Host "[*] Submitting feedback..." -ForegroundColor Yellow
                Submit-IFMOSMLFeedback `
                    -DocumentId $result.document_id `
                    -CorrectCategory $selectedCat `
                    -WasCorrect $wasCorrect `
                    -Comment "User review" | Out-Null

                $existingFeedback[$result.document_id] = $feedback

                if ($wasCorrect) {
                    Write-Host "[OK] Correct prediction confirmed!" -ForegroundColor Green
                    $feedbackStats.correct++
                } else {
                    Write-Host "[OK] Feedback recorded: $selectedCat" -ForegroundColor Green
                    $feedbackStats.corrected++
                }

                # Save feedback periodically
                if (($feedbackStats.reviewed + 1) % 10 -eq 0) {
                    $existingFeedback.Values | ConvertTo-Json -Depth 5 | Out-File -FilePath $FeedbackPath
                }

            } else {
                Write-Host "[ERROR] Invalid category number" -ForegroundColor Red
                Start-Sleep -Seconds 1
                continue
            }
        }
        default {
            Write-Host "[ERROR] Invalid choice" -ForegroundColor Red
            Start-Sleep -Seconds 1
            continue
        }
    }

    $feedbackStats.reviewed++

    if ($choice -match '^[qQaA]$') {
        break
    }
}

# Final save
$existingFeedback.Values | ConvertTo-Json -Depth 5 | Out-File -FilePath $FeedbackPath

# Display statistics
Clear-Host
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Feedback Collection Complete" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Total Documents:       $($feedbackStats.total)" -ForegroundColor Yellow
Write-Host "Reviewed:              $($feedbackStats.reviewed)" -ForegroundColor Green
Write-Host "  - Correct:           $($feedbackStats.correct)" -ForegroundColor Green
Write-Host "  - Corrected:         $($feedbackStats.corrected)" -ForegroundColor Yellow
Write-Host "Skipped:               $($feedbackStats.skipped)" -ForegroundColor Gray
Write-Host "`nFeedback saved to: $FeedbackPath`n" -ForegroundColor Gray

# Get updated ML statistics
Write-Host "[*] Fetching ML system statistics..." -ForegroundColor Yellow
$mlStats = Get-IFMOSMLStats
Write-Host "`nML System Statistics:" -ForegroundColor Cyan
Write-Host "  Total Documents:     $($mlStats.total_documents)" -ForegroundColor Gray
Write-Host "  Total Feedback:      $($mlStats.total_feedback)" -ForegroundColor Gray
Write-Host "  Correct Predictions: $($mlStats.correct_predictions)" -ForegroundColor Gray
Write-Host "  Active Categories:   $($mlStats.active_categories)" -ForegroundColor Gray

if ($mlStats.total_feedback -ge 100) {
    Write-Host "`n[READY] You have enough labeled data to train the classifier!" -ForegroundColor Green
    Write-Host "Next step: .\train_classifier.ps1`n" -ForegroundColor Yellow
} else {
    $remaining = 100 - $mlStats.total_feedback
    Write-Host "`n[INFO] Need $remaining more labeled documents before training (100 minimum recommended)" -ForegroundColor Yellow
    Write-Host "Continue processing and reviewing more documents.`n" -ForegroundColor Gray
}
