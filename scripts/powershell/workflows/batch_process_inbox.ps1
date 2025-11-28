# Batch Process All Inbox Files Through IFMOS ML
# Processes all documents and saves results for review

param(
    [string]$InboxPath = "C:\Users\kjfle\00_Inbox\To_Review",
    [string]$ResultsPath = "C:\Users\kjfle\ml_batch_results",
    [int]$MaxFiles = 0,  # 0 = process all
    [switch]$SkipExisting
)

Import-Module C:\Users\kjfle\Projects\intelligent-file-management-system\scripts\powershell\IFMOS-ML-Bridge.psm1

# Create results directory
if (-not (Test-Path $ResultsPath)) {
    New-Item -ItemType Directory -Path $ResultsPath | Out-Null
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "IFMOS ML Batch Processing" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Check server health
Write-Host "[*] Checking ML server..." -ForegroundColor Yellow
if (-not (Test-IFMOSMLServer)) {
    Write-Host "[ERROR] ML server is not running!" -ForegroundColor Red
    Write-Host "Please start the server first:" -ForegroundColor Yellow
    Write-Host "  Start-IFMOSMLServer" -ForegroundColor Gray
    exit 1
}
Write-Host "[OK] ML server is running`n" -ForegroundColor Green

# Get all files to process
$allFiles = Get-ChildItem -Path $InboxPath -File | Sort-Object Name
if ($MaxFiles -gt 0) {
    $allFiles = $allFiles | Select-Object -First $MaxFiles
}

Write-Host "Files to process: $($allFiles.Count)" -ForegroundColor Yellow
Write-Host "Results directory: $ResultsPath`n" -ForegroundColor Gray

# Load existing results if skipping
$processedFiles = @()
if ($SkipExisting -and (Test-Path "$ResultsPath\batch_results.json")) {
    $existing = Get-Content "$ResultsPath\batch_results.json" | ConvertFrom-Json
    $processedFiles = $existing | ForEach-Object { $_.file_name }
    Write-Host "Skipping $($processedFiles.Count) already processed files`n" -ForegroundColor Gray
}

# Processing statistics
$stats = @{
    total = $allFiles.Count
    processed = 0
    succeeded = 0
    failed = 0
    skipped = 0
    startTime = Get-Date
}

$results = @()

# Process each file
$fileNum = 0
foreach ($file in $allFiles) {
    $fileNum++

    # Skip if already processed
    if ($processedFiles -contains $file.Name) {
        $stats.skipped++
        Write-Host "[$fileNum/$($stats.total)] SKIPPED: $($file.Name)" -ForegroundColor Gray
        continue
    }

    Write-Host "[$fileNum/$($stats.total)] Processing: $($file.Name)" -ForegroundColor Yellow

    try {
        # Process document
        $response = Invoke-IFMOSMLProcess -FilePath $file.FullName

        if ($response -and $response.success) {
            $stats.succeeded++

            # Create result summary
            $result = @{
                file_name = $file.Name
                file_path = $file.FullName
                document_id = $response.document_id
                prediction_id = $response.prediction_id
                extraction_method = $response.extraction.method
                text_length = $response.extraction.text.Length
                document_type = $response.analysis.document_type
                entities_count = $response.analysis.entities.Count
                predicted_category = $response.prediction.predicted_category
                confidence = $response.prediction.confidence
                processing_time = (Get-Date) - $stats.startTime
                timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
            }

            $results += $result

            Write-Host "  [SUCCESS] Doc ID: $($response.document_id) | " -NoNewline -ForegroundColor Green
            Write-Host "Type: $($response.analysis.document_type) | " -NoNewline -ForegroundColor Gray
            Write-Host "Entities: $($response.analysis.entities.Count)" -ForegroundColor Gray

            # Save individual result
            $response | ConvertTo-Json -Depth 10 | Out-File -FilePath "$ResultsPath\doc_$($response.document_id).json"

        } else {
            $stats.failed++
            Write-Host "  [FAILED] Processing failed" -ForegroundColor Red
        }

        $stats.processed++

        # Save progress periodically (every 10 files)
        if ($stats.processed % 10 -eq 0) {
            $results | ConvertTo-Json -Depth 5 | Out-File -FilePath "$ResultsPath\batch_results.json"
            Write-Host "  [*] Progress saved ($($stats.processed)/$($stats.total))`n" -ForegroundColor Cyan
        }

    } catch {
        $stats.failed++
        Write-Host "  [ERROR] $($_.Exception.Message)" -ForegroundColor Red
    }

    # Brief pause to avoid overwhelming the server
    Start-Sleep -Milliseconds 100
}

# Final save
$results | ConvertTo-Json -Depth 5 | Out-File -FilePath "$ResultsPath\batch_results.json"

# Calculate statistics
$stats.endTime = Get-Date
$stats.duration = ($stats.endTime - $stats.startTime).TotalSeconds

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Batch Processing Complete" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Total Files:      $($stats.total)" -ForegroundColor Yellow
Write-Host "Processed:        $($stats.processed)" -ForegroundColor Green
Write-Host "  - Succeeded:    $($stats.succeeded)" -ForegroundColor Green
Write-Host "  - Failed:       $($stats.failed)" -ForegroundColor Red
Write-Host "Skipped:          $($stats.skipped)" -ForegroundColor Gray
Write-Host "Duration:         $([Math]::Round($stats.duration, 2)) seconds" -ForegroundColor Yellow
Write-Host "Avg per file:     $([Math]::Round($stats.duration / $stats.processed, 2)) seconds`n" -ForegroundColor Yellow

Write-Host "Results saved to: $ResultsPath" -ForegroundColor Gray
Write-Host "  - batch_results.json (summary)" -ForegroundColor Gray
Write-Host "  - doc_*.json (individual results)`n" -ForegroundColor Gray

# Create summary report
$reportPath = "$ResultsPath\processing_summary.txt"
$report = @"
IFMOS ML Batch Processing Summary
==================================
Date: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

Statistics:
-----------
Total Files:      $($stats.total)
Processed:        $($stats.processed)
  - Succeeded:    $($stats.succeeded)
  - Failed:       $($stats.failed)
Skipped:          $($stats.skipped)
Duration:         $([Math]::Round($stats.duration, 2)) seconds
Avg per file:     $([Math]::Round($stats.duration / $stats.processed, 2)) seconds

Document Types Found:
--------------------
$($results | Group-Object document_type | Sort-Object Count -Descending | ForEach-Object { "  $($_.Name): $($_.Count) files" } | Out-String)

Extraction Methods:
------------------
$($results | Group-Object extraction_method | Sort-Object Count -Descending | ForEach-Object { "  $($_.Name): $($_.Count) files" } | Out-String)

Next Steps:
----------
1. Review results in: $ResultsPath
2. Run feedback collection: .\collect_feedback.ps1
3. Train model after 100+ labeled documents
"@

$report | Out-File -FilePath $reportPath -Encoding UTF8
Write-Host "Summary report saved to: $reportPath`n" -ForegroundColor Gray

Write-Host "Next step: Review and provide feedback for classification training" -ForegroundColor Cyan
Write-Host "  .\collect_feedback.ps1`n" -ForegroundColor Yellow
