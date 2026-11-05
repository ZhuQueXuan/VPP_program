$ErrorActionPreference = 'Stop'
$reportInput = 'D:\myDocu\project_postg\VPP_program\outputs\课题一B1与B2算法阶段汇报_20261029.docx'
$reportPdf = 'D:\myDocu\project_postg\VPP_program\outputs\课题一B1与B2算法阶段汇报_20261029.pdf'
$reportReceipt = 'D:\myDocu\project_postg\VPP_program\work\b1_b2_meeting_report_20261029\word_export.json'
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
  @{ status = 'success'; renderer = 'Microsoft Word native PDF export'; word_version = $reportWord.Version; page_count = $reportPages; input = $reportInput; pdf = $reportPdf } | ConvertTo-Json | Set-Content -LiteralPath $reportReceipt -Encoding utf8
  Write-Output "Exported report PDF; pages=$reportPages"
} finally {
  if ($null -ne $reportDoc) { $reportDoc.Close(0); [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($reportDoc) | Out-Null }
  if ($null -ne $reportWord) { $reportWord.Quit(); [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($reportWord) | Out-Null }
}
