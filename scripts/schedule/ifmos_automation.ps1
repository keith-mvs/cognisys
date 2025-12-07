# CogniSys Automated Task Scheduler
# Runs periodic ML maintenance tasks: pattern detection, auto-retraining, cleanup

param(
    [string]$Task = "all",
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"
$ProjectRoot = "C:\Users\kjfle\Projects\intelligent-file-management-system"
$PythonExe = "$ProjectRoot\venv\Scripts\python.exe"
$LogDir = "$ProjectRoot\logs\automation"

# Create log directory
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log {
    param($Message, $Level = "INFO")
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogMessage = "[$Timestamp] [$Level] $Message"

    if ($Verbose) {
        Write-Host $LogMessage
    }

    Add-Content -Path "$LogDir\automation_$(Get-Date -Format 'yyyyMMdd').log" -Value $LogMessage
}

function Run-PatternDetection {
    Write-Log "Running pattern detection analysis..."

    try {
        & $PythonExe "$ProjectRoot\scripts\ml\pattern_detector.py"
        Write-Log "Pattern detection completed successfully"
        return $true
    }
    catch {
        Write-Log "Pattern detection failed: $_" "ERROR"
        return $false
    }
}

function Run-AutoRetrain {
    Write-Log "Checking auto-retraining criteria..."

    try {
        & $PythonExe "$ProjectRoot\scripts\ml\auto_retrain.py"
        Write-Log "Auto-retrain check completed"
        return $true
    }
    catch {
        Write-Log "Auto-retrain failed: $_" "ERROR"
        return $false
    }
}

function Run-DatabaseCleanup {
    Write-Log "Running database cleanup..."

    try {
        $DbPath = "$ProjectRoot\cognisys\data\training\cognisys_ml.db"

        # Vacuum database to reclaim space
        & $PythonExe -c @"
import sqlite3
conn = sqlite3.connect('$DbPath')
conn.execute('VACUUM')
conn.execute('ANALYZE')
conn.close()
print('Database optimized')
"@

        Write-Log "Database cleanup completed"
        return $true
    }
    catch {
        Write-Log "Database cleanup failed: $_" "ERROR"
        return $false
    }
}

function Run-ReportGeneration {
    Write-Log "Generating weekly summary report..."

    try {
        # Generate statistics summary
        $StatsOutput = & $PythonExe -c @"
import sqlite3
conn = sqlite3.connect('$ProjectRoot\cognisys\data\training\cognisys_ml.db')
cursor = conn.cursor()

cursor.execute('SELECT COUNT(*) FROM documents')
total = cursor.fetchone()[0]

cursor.execute('''
    SELECT doc_type, COUNT(*)
    FROM documents
    WHERE datetime(created_at) > datetime('now', '-7 days')
    GROUP BY doc_type
    ORDER BY COUNT(*) DESC
    LIMIT 5
''')
top_types = cursor.fetchall()

print(f'Total Documents: {total}')
print('Top 5 Types (Last 7 Days):')
for doc_type, count in top_types:
    print(f'  - {doc_type}: {count}')

conn.close()
"@

        $ReportPath = "$ProjectRoot\reports\weekly_summary_$(Get-Date -Format 'yyyyMMdd').txt"
        New-Item -ItemType Directory -Force -Path "$ProjectRoot\reports" | Out-Null

        @"
CogniSys Weekly Summary Report
Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
========================================

$StatsOutput

========================================
"@ | Out-File -FilePath $ReportPath

        Write-Log "Report generated: $ReportPath"
        return $true
    }
    catch {
        Write-Log "Report generation failed: $_" "ERROR"
        return $false
    }
}

# Main execution
Write-Log "========== CogniSys Automation Start =========="
Write-Log "Task: $Task"

$results = @{}

switch ($Task) {
    "pattern" {
        $results['pattern_detection'] = Run-PatternDetection
    }
    "retrain" {
        $results['auto_retrain'] = Run-AutoRetrain
    }
    "cleanup" {
        $results['database_cleanup'] = Run-DatabaseCleanup
    }
    "report" {
        $results['report_generation'] = Run-ReportGeneration
    }
    "all" {
        $results['pattern_detection'] = Run-PatternDetection
        $results['auto_retrain'] = Run-AutoRetrain
        $results['database_cleanup'] = Run-DatabaseCleanup
        $results['report_generation'] = Run-ReportGeneration
    }
    default {
        Write-Log "Unknown task: $Task" "ERROR"
        exit 1
    }
}

# Summary
Write-Log "========== Automation Summary =========="
foreach ($taskName in $results.Keys) {
    $status = if ($results[$taskName]) { "SUCCESS" } else { "FAILED" }
    Write-Log "$taskName : $status"
}
Write-Log "========== CogniSys Automation Complete =========="

# Return exit code
if ($results.Values -contains $false) {
    exit 1
} else {
    exit 0
}
