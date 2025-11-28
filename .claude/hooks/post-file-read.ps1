# Post File Read Hook for IFMOS (PowerShell)
param($FilePath)

$FileExtension = [System.IO.Path]::GetExtension($FilePath).TrimStart('.')

# Check if this is a document type that IFMOS can classify
$ClassifiableExtensions = @('pdf', 'docx', 'xlsx', 'txt', 'png', 'jpg', 'jpeg', 'html', 'py', 'ps1', 'yaml', 'json')

if ($FileExtension -in $ClassifiableExtensions) {
    if ($FilePath -match '00_Inbox|To_Review') {
        Write-Output "[IFMOS] This document appears to be unclassified. Would you like me to:"
        Write-Output "  1. Classify it using the ML pipeline"
        Write-Output "  2. Query similar documents in the database"
        Write-Output "  3. Show classification statistics"
    }
}

exit 0
