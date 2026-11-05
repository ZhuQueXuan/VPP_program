$ErrorActionPreference = 'Stop'
$reportInput = 'D:\myDocu\project_postg\VPP_program\outputs\课题一B1算法研究报告_通用方法对比版_20261029.docx'
$reportPdf = 'D:\myDocu\project_postg\VPP_program\outputs\课题一B1算法研究报告_通用方法对比版_20261029.pdf'
$reportReceipt = 'D:\myDocu\project_postg\VPP_program\work\b1_mainline_20261029\report\word_export.json'
$reportWord = $null
$reportDoc = $null
try {
  $reportWord = New-Object -ComObject Word.Application
  $reportWord.Visible = $false
  $reportWord.DisplayAlerts = 0
  $reportDoc = $reportWord.Documents.Open($reportInput, $false, $true)
  $reportDoc.Repaginate()
  $reportDoc.ExportAsFixedFormat($reportPdf, 17)
  $reportPages = $reportDoc.ComputeStatistics(2)
  @{ status='success'; renderer='Microsoft Word native PDF export'; word_version=$reportWord.Version; page_count=$reportPages; input=$reportInput; pdf=$reportPdf; docx_sha256=(Get-FileHash -LiteralPath $reportInput -Algorithm SHA256).Hash; pdf_sha256=(Get-FileHash -LiteralPath $reportPdf -Algorithm SHA256).Hash } | ConvertTo-Json | Set-Content -LiteralPath $reportReceipt -Encoding utf8
  Write-Output "Exported report PDF; pages=$reportPages"
} finally {
  if ($null -ne $reportDoc) { $reportDoc.Close(0); [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($reportDoc) | Out-Null }
  if ($null -ne $reportWord) {
    if ($reportWord.Documents.Count -eq 0) { $reportWord.Quit() }
    [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($reportWord) | Out-Null
  }
}
