# Analyze inbox files and suggest categories based on filenames
$inboxPath = "C:\Users\kjfle\00_Inbox\To_Review"
$files = Get-ChildItem $inboxPath

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Inbox File Analysis" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Total Files: $($files.Count)" -ForegroundColor Yellow

# Extract keywords from filenames
$keywords = @{}
foreach ($file in $files) {
    $name = $file.BaseName -replace '^\d{4}-\d{2}-\d{2}_review_', ''

    # Split on common separators and get key terms
    $parts = $name -split '[_\[\]\s-]' | Where-Object { $_.Length -gt 2 }

    foreach ($part in $parts) {
        $lower = $part.ToLower()
        if ($keywords.ContainsKey($lower)) {
            $keywords[$lower]++
        } else {
            $keywords[$lower] = 1
        }
    }
}

Write-Host "`n--- Top Keywords (frequency) ---" -ForegroundColor Yellow
$keywords.GetEnumerator() |
    Sort-Object -Property Value -Descending |
    Select-Object -First 20 |
    ForEach-Object { Write-Host "  $($_.Key): $($_.Value)" }

# File type analysis
Write-Host "`n--- File Types ---" -ForegroundColor Yellow
$files | Group-Object Extension | Sort-Object Count -Descending | ForEach-Object {
    Write-Host "  $($_.Name): $($_.Count) files"
}

# Suggest categories based on keywords
Write-Host "`n--- Suggested Categories ---" -ForegroundColor Green

$categories = @(
    @{Name="Legal_CCO"; Pattern="cco"; Description="CCO legal documents"},
    @{Name="Healthcare_Medical"; Pattern="quest|billing|medical"; Description="Medical and healthcare documents"},
    @{Name="Legal_PropertyTax"; Pattern="property|tax|code"; Description="Property tax and legal code documents"},
    @{Name="Real_Estate"; Pattern="realty|notes"; Description="Real estate and property documents"},
    @{Name="Education"; Pattern="education|childhood|mexico"; Description="Education-related documents"},
    @{Name="Technology"; Pattern="mozilla|recovery|onedrive"; Description="Technology and account documents"},
    @{Name="Financial_General"; Pattern="value|insert"; Description="General financial documents"},
    @{Name="Personal_Letters"; Pattern="letter"; Description="Personal correspondence"},
    @{Name="Personal_Documents"; Pattern="temporary|id"; Description="Personal identification documents"},
    @{Name="Work_Documents"; Pattern="text|document|doc"; Description="General work documents"}
)

foreach ($cat in $categories) {
    $matchCount = ($files | Where-Object { $_.Name -match $cat.Pattern }).Count
    if ($matchCount -gt 0) {
        Write-Host "  $($cat.Name): $matchCount files - $($cat.Description)" -ForegroundColor Cyan
    }
}

Write-Host "`n========================================`n" -ForegroundColor Cyan

# Generate category creation script
$scriptPath = "C:\Users\kjfle\create_categories.ps1"
$script = @"
# Generated Category Creation Script
# Based on analysis of C:\Users\kjfle\00_Inbox\To_Review

Import-Module C:\Users\kjfle\Projects\intelligent-file-management-system\IFMOS-ML-Bridge.psm1

Write-Host "Creating IFMOS ML Categories..." -ForegroundColor Cyan

"@

foreach ($cat in $categories) {
    $matchCount = ($files | Where-Object { $_.Name -match $cat.Pattern }).Count
    if ($matchCount -gt 0) {
        $script += @"

# Category: $($cat.Name) ($matchCount files)
Add-IFMOSMLCategory ``
    -CategoryName "$($cat.Name)" ``
    -Description "$($cat.Description)" ``
    -PatternPath "C:\Users\kjfle\30_Financial\$($cat.Name)"
Write-Host "  [+] Created: $($cat.Name)" -ForegroundColor Green

"@
    }
}

$script += @"

Write-Host "`nAll categories created!" -ForegroundColor Green
Get-IFMOSMLCategories | Format-Table category_name, description
"@

$script | Out-File -FilePath $scriptPath -Encoding UTF8
Write-Host "Category creation script saved to: $scriptPath" -ForegroundColor Gray
