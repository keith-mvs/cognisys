$response = Invoke-RestMethod -Uri 'http://127.0.0.1:5000/stats' -Method Get
$response.statistics | Format-List
$response.statistics | ConvertTo-Json -Depth 3
