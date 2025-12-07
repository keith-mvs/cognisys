# CogniSys ML Bridge - PowerShell Module
# Provides functions to interact with Python ML API

# API Configuration
$script:API_BASE_URL = "http://127.0.0.1:5000"
$script:API_PROCESS = $null

<#
.SYNOPSIS
    Starts the CogniSys ML API server in the background
.DESCRIPTION
    Launches the Flask API server using the PyTorch virtual environment
.EXAMPLE
    Start-IFMOSMLServer
#>
function Start-IFMOSMLServer {
    [CmdletBinding()]
    param()

    Write-Host "[+] Starting CogniSys ML API Server..." -ForegroundColor Cyan

    $pythonVenv = "C:\Users\kjfle\Projects\intelligent-file-management-system\venv\Scripts\python.exe"
    $apiScript = "C:\Users\kjfle\Projects\intelligent-file-management-system\ifmos\ml\api\flask_server.py"

    if (-not (Test-Path $pythonVenv)) {
        Write-Error "Python venv not found: $pythonVenv"
        return $false
    }

    if (-not (Test-Path $apiScript)) {
        Write-Error "API script not found: $apiScript"
        return $false
    }

    # Start API server in background
    $script:API_PROCESS = Start-Process -FilePath $pythonVenv `
        -ArgumentList $apiScript `
        -WindowStyle Hidden `
        -PassThru

    # Wait for API to be ready
    $maxRetries = 30
    $retryCount = 0
    $isReady = $false

    while ($retryCount -lt $maxRetries -and -not $isReady) {
        Start-Sleep -Milliseconds 500
        try {
            $response = Invoke-RestMethod -Uri "$script:API_BASE_URL/health" -Method Get -TimeoutSec 2
            if ($response.status -eq "healthy") {
                $isReady = $true
            }
        } catch {
            $retryCount++
        }
    }

    if ($isReady) {
        Write-Host "[SUCCESS] ML API Server started (PID: $($script:API_PROCESS.Id))" -ForegroundColor Green
        if ($response.gpu_available) {
            Write-Host "          GPU Detected: $($response.gpu_name)" -ForegroundColor Green
        }
        return $true
    } else {
        Write-Error "ML API Server failed to start after $maxRetries attempts"
        return $false
    }
}

<#
.SYNOPSIS
    Stops the CogniSys ML API server
.EXAMPLE
    Stop-IFMOSMLServer
#>
function Stop-IFMOSMLServer {
    [CmdletBinding()]
    param()

    Write-Host "[-] Stopping CogniSys ML API Server..." -ForegroundColor Yellow

    try {
        # Try graceful shutdown first
        Invoke-RestMethod -Uri "$script:API_BASE_URL/shutdown" -Method Post -TimeoutSec 5 | Out-Null
        Start-Sleep -Seconds 2
    } catch {
        # Force stop if graceful shutdown fails
        if ($script:API_PROCESS -and -not $script:API_PROCESS.HasExited) {
            Stop-Process -Id $script:API_PROCESS.Id -Force
        }
    }

    Write-Host "[OK] ML API Server stopped" -ForegroundColor Gray
}

<#
.SYNOPSIS
    Process a document through the complete ML pipeline
.DESCRIPTION
    Extracts content, analyzes text, classifies, and stores in database
.PARAMETER FilePath
    Path to document file
.EXAMPLE
    $result = Invoke-IFMOSMLProcess -FilePath "C:\path\to\document.pdf"
#>
function Invoke-IFMOSMLProcess {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$FilePath
    )

    if (-not (Test-Path -LiteralPath $FilePath)) {
        Write-Error "File not found: $FilePath"
        return $null
    }

    # Use -LiteralPath to handle brackets and special characters in filenames
    $body = @{
        file_path = (Resolve-Path -LiteralPath $FilePath).Path
    } | ConvertTo-Json

    try {
        $response = Invoke-RestMethod `
            -Uri "$script:API_BASE_URL/process/document" `
            -Method Post `
            -Body $body `
            -ContentType "application/json" `
            -TimeoutSec 120

        return $response
    } catch {
        Write-Error "ML processing failed: $_"
        return $null
    }
}

<#
.SYNOPSIS
    Submit feedback for a classification
.PARAMETER DocumentId
    Database document ID
.PARAMETER CorrectCategory
    The correct category for the document
.PARAMETER PredictionId
    Optional prediction ID
.PARAMETER WasCorrect
    Whether the prediction was correct
.EXAMPLE
    Submit-IFMOSMLFeedback -DocumentId 123 -CorrectCategory "Tax_2024_1099" -WasCorrect $true
#>
function Submit-IFMOSMLFeedback {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [int]$DocumentId,

        [Parameter(Mandatory=$true)]
        [string]$CorrectCategory,

        [int]$PredictionId,

        [bool]$WasCorrect = $false,

        [string]$Comment
    )

    $body = @{
        document_id = $DocumentId
        correct_category = $CorrectCategory
        was_correct = $WasCorrect
    }

    if ($PredictionId) {
        $body.prediction_id = $PredictionId
    }

    if ($Comment) {
        $body.comment = $Comment
    }

    $bodyJson = $body | ConvertTo-Json

    try {
        $response = Invoke-RestMethod `
            -Uri "$script:API_BASE_URL/feedback/submit" `
            -Method Post `
            -Body $bodyJson `
            -ContentType "application/json"

        return $response
    } catch {
        Write-Error "Feedback submission failed: $_"
        return $null
    }
}

<#
.SYNOPSIS
    Get ML system statistics
.EXAMPLE
    Get-IFMOSMLStats
#>
function Get-IFMOSMLStats {
    [CmdletBinding()]
    param()

    try {
        $response = Invoke-RestMethod `
            -Uri "$script:API_BASE_URL/stats" `
            -Method Get

        return $response.statistics
    } catch {
        Write-Error "Failed to retrieve stats: $_"
        return $null
    }
}

<#
.SYNOPSIS
    Get or add categories
.PARAMETER CategoryName
    Category name to add (for POST)
.PARAMETER Description
    Category description
.PARAMETER PatternPath
    Legacy pattern-based destination path
.EXAMPLE
    Get-IFMOSMLCategories
    Add-IFMOSMLCategory -CategoryName "Tax_2024_W2" -Description "W-2 forms for 2024"
#>
function Get-IFMOSMLCategories {
    [CmdletBinding()]
    param()

    try {
        $response = Invoke-RestMethod `
            -Uri "$script:API_BASE_URL/categories" `
            -Method Get

        return $response.categories
    } catch {
        Write-Error "Failed to retrieve categories: $_"
        return $null
    }
}

function Add-IFMOSMLCategory {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$CategoryName,

        [string]$Description,

        [string]$PatternPath
    )

    $body = @{
        category_name = $CategoryName
    }

    if ($Description) { $body.description = $Description }
    if ($PatternPath) { $body.pattern_path = $PatternPath }

    $bodyJson = $body | ConvertTo-Json

    try {
        $response = Invoke-RestMethod `
            -Uri "$script:API_BASE_URL/categories" `
            -Method Post `
            -Body $bodyJson `
            -ContentType "application/json"

        return $response
    } catch {
        Write-Error "Failed to add category: $_"
        return $null
    }
}

<#
.SYNOPSIS
    Test if ML API server is running
.EXAMPLE
    if (Test-IFMOSMLServer) { Write-Host "Server is running" }
#>
function Test-IFMOSMLServer {
    [CmdletBinding()]
    param()

    try {
        $response = Invoke-RestMethod -Uri "$script:API_BASE_URL/health" -Method Get -TimeoutSec 2
        return ($response.status -eq "healthy")
    } catch {
        return $false
    }
}

# Export module functions
Export-ModuleMember -Function @(
    'Start-IFMOSMLServer',
    'Stop-IFMOSMLServer',
    'Invoke-IFMOSMLProcess',
    'Submit-IFMOSMLFeedback',
    'Get-IFMOSMLStats',
    'Get-IFMOSMLCategories',
    'Add-IFMOSMLCategory',
    'Test-IFMOSMLServer'
)
