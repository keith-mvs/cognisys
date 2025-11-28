$response = Invoke-RestMethod -Uri 'http://127.0.0.1:5000/health' -Method Get -TimeoutSec 30
Write-Host "Server Status: $($response.status)"
Write-Host "GPU Available: $($response.gpu_available)"
Write-Host "GPU Name: $($response.gpu_name)"
$response | ConvertTo-Json -Depth 3
