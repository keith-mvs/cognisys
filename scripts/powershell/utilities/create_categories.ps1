# Generated Category Creation Script
# Based on analysis of C:\Users\kjfle\00_Inbox\To_Review

Import-Module C:\Users\kjfle\Projects\intelligent-file-management-system\IFMOS-ML-Bridge.psm1

Write-Host "Creating IFMOS ML Categories..." -ForegroundColor Cyan

# Category: Legal_CCO (78 files)
Add-IFMOSMLCategory `
    -CategoryName "Legal_CCO" `
    -Description "CCO legal documents" `
    -PatternPath "C:\Users\kjfle\30_Financial\Legal_CCO"
Write-Host "  [+] Created: Legal_CCO" -ForegroundColor Green

# Category: Healthcare_Medical (1 files)
Add-IFMOSMLCategory `
    -CategoryName "Healthcare_Medical" `
    -Description "Medical and healthcare documents" `
    -PatternPath "C:\Users\kjfle\30_Financial\Healthcare_Medical"
Write-Host "  [+] Created: Healthcare_Medical" -ForegroundColor Green

# Category: Legal_PropertyTax (1 files)
Add-IFMOSMLCategory `
    -CategoryName "Legal_PropertyTax" `
    -Description "Property tax and legal code documents" `
    -PatternPath "C:\Users\kjfle\30_Financial\Legal_PropertyTax"
Write-Host "  [+] Created: Legal_PropertyTax" -ForegroundColor Green

# Category: Real_Estate (1 files)
Add-IFMOSMLCategory `
    -CategoryName "Real_Estate" `
    -Description "Real estate and property documents" `
    -PatternPath "C:\Users\kjfle\30_Financial\Real_Estate"
Write-Host "  [+] Created: Real_Estate" -ForegroundColor Green

# Category: Education (1 files)
Add-IFMOSMLCategory `
    -CategoryName "Education" `
    -Description "Education-related documents" `
    -PatternPath "C:\Users\kjfle\30_Financial\Education"
Write-Host "  [+] Created: Education" -ForegroundColor Green

# Category: Technology (2 files)
Add-IFMOSMLCategory `
    -CategoryName "Technology" `
    -Description "Technology and account documents" `
    -PatternPath "C:\Users\kjfle\30_Financial\Technology"
Write-Host "  [+] Created: Technology" -ForegroundColor Green

# Category: Financial_General (1 files)
Add-IFMOSMLCategory `
    -CategoryName "Financial_General" `
    -Description "General financial documents" `
    -PatternPath "C:\Users\kjfle\30_Financial\Financial_General"
Write-Host "  [+] Created: Financial_General" -ForegroundColor Green

# Category: Personal_Letters (1 files)
Add-IFMOSMLCategory `
    -CategoryName "Personal_Letters" `
    -Description "Personal correspondence" `
    -PatternPath "C:\Users\kjfle\30_Financial\Personal_Letters"
Write-Host "  [+] Created: Personal_Letters" -ForegroundColor Green

# Category: Personal_Documents (1 files)
Add-IFMOSMLCategory `
    -CategoryName "Personal_Documents" `
    -Description "Personal identification documents" `
    -PatternPath "C:\Users\kjfle\30_Financial\Personal_Documents"
Write-Host "  [+] Created: Personal_Documents" -ForegroundColor Green

# Category: Work_Documents (6 files)
Add-IFMOSMLCategory `
    -CategoryName "Work_Documents" `
    -Description "General work documents" `
    -PatternPath "C:\Users\kjfle\30_Financial\Work_Documents"
Write-Host "  [+] Created: Work_Documents" -ForegroundColor Green

Write-Host "
All categories created!" -ForegroundColor Green
Get-IFMOSMLCategories | Format-Table category_name, description
