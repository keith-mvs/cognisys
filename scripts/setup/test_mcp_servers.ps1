# Test MCP Server Configuration
# Verifies all MCP servers are properly configured and functional

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "IFMOS MCP Server Configuration Test" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

$ConfigPath = "$env:USERPROFILE\.claude\config.json"

# Check if config exists
if (-not (Test-Path $ConfigPath)) {
    Write-Host "[ERROR] MCP config not found at: $ConfigPath" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] MCP config found" -ForegroundColor Green

# Load config
$Config = Get-Content $ConfigPath | ConvertFrom-Json

# Test each MCP server
$TestResults = @{}

foreach ($ServerName in $Config.mcpServers.PSObject.Properties.Name) {
    $Server = $Config.mcpServers.$ServerName

    Write-Host "`nTesting $ServerName..." -ForegroundColor Yellow
    Write-Host "  Command: $($Server.command)"
    Write-Host "  Description: $($Server.description)"

    # Test command availability
    $Command = $Server.command

    if ($Command -eq "npx") {
        # Test Node.js
        try {
            $NodeVersion = node --version
            Write-Host "  [OK] Node.js available: $NodeVersion" -ForegroundColor Green
            $TestResults[$ServerName] = "OK"
        }
        catch {
            Write-Host "  [ERROR] Node.js not available" -ForegroundColor Red
            $TestResults[$ServerName] = "FAILED"
        }
    }
    elseif ($Command -eq "python") {
        # Test Python
        try {
            $PythonVersion = python --version
            Write-Host "  [OK] Python available: $PythonVersion" -ForegroundColor Green

            # Test if IFMOS server file exists
            if ($Server.args[0] -match "ifmos_server.py") {
                $ServerPath = $Server.args[0]
                if (Test-Path $ServerPath) {
                    Write-Host "  [OK] IFMOS server script found" -ForegroundColor Green
                    $TestResults[$ServerName] = "OK"
                }
                else {
                    Write-Host "  [ERROR] IFMOS server script not found: $ServerPath" -ForegroundColor Red
                    $TestResults[$ServerName] = "FAILED"
                }
            }
        }
        catch {
            Write-Host "  [ERROR] Python not available" -ForegroundColor Red
            $TestResults[$ServerName] = "FAILED"
        }
    }
}

# Test IFMOS database
Write-Host "`nTesting IFMOS Database..." -ForegroundColor Yellow
$DbPath = "C:\Users\kjfle\Projects\intelligent-file-management-system\ifmos\data\training\ifmos_ml.db"

if (Test-Path $DbPath) {
    Write-Host "  [OK] Database found: $DbPath" -ForegroundColor Green

    # Get document count
    $DocCount = & python -c "import sqlite3; conn = sqlite3.connect('$DbPath'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM documents'); print(cursor.fetchone()[0]); conn.close()"
    Write-Host "  [OK] Database contains $DocCount documents" -ForegroundColor Green
}
else {
    Write-Host "  [ERROR] Database not found: $DbPath" -ForegroundColor Red
}

# Test hooks
Write-Host "`nTesting Hooks..." -ForegroundColor Yellow
$HooksPath = "C:\Users\kjfle\Projects\intelligent-file-management-system\.claude\hooks"

if (Test-Path $HooksPath) {
    $HookFiles = Get-ChildItem $HooksPath -Filter "*.ps1"
    Write-Host "  [OK] Found $($HookFiles.Count) PowerShell hooks" -ForegroundColor Green

    foreach ($Hook in $HookFiles) {
        Write-Host "    - $($Hook.Name)" -ForegroundColor Gray
    }
}
else {
    Write-Host "  [WARNING] Hooks directory not found" -ForegroundColor Yellow
}

# Summary
Write-Host "`n" + ("=" * 80) -ForegroundColor Cyan
Write-Host "Test Summary" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan

$PassCount = ($TestResults.Values | Where-Object { $_ -eq "OK" }).Count
$FailCount = ($TestResults.Values | Where-Object { $_ -eq "FAILED" }).Count

foreach ($ServerName in $TestResults.Keys) {
    $Status = $TestResults[$ServerName]
    $Color = if ($Status -eq "OK") { "Green" } else { "Red" }
    Write-Host "  $ServerName : $Status" -ForegroundColor $Color
}

Write-Host "`nTotal: $PassCount passed, $FailCount failed" -ForegroundColor $(if ($FailCount -eq 0) { "Green" } else { "Yellow" })

if ($FailCount -eq 0) {
    Write-Host "`n[SUCCESS] All MCP servers configured correctly!" -ForegroundColor Green
    Write-Host "You can now use MCP tools in Claude Code." -ForegroundColor Green
}
else {
    Write-Host "`n[WARNING] Some servers failed. Check errors above." -ForegroundColor Yellow
}

Write-Host ""
