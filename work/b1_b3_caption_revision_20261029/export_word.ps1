$ErrorActionPreference = 'Stop'
$reportInput = 'D:\myDocu\project_postg\VPP_program\outputs\课题一B1至B3算法阶段研究报告_图注修订版_20261029.docx'
$reportPdf = 'D:\myDocu\project_postg\VPP_program\outputs\课题一B1至B3算法阶段研究报告_图注修订版_20261029.pdf'
$reportReceipt = 'D:\myDocu\project_postg\VPP_program\work\b1_b3_caption_revision_20261029\word_export.json'
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
  @{ status = 'success'; renderer = 'Microsoft Word native PDF export'; word_version = $reportWord.Version; page_count = $reportPages; input = $reportInput; input_sha256 = (Get-FileHash -LiteralPath $reportInput -Algorithm SHA256).Hash.ToLower(); pdf = $reportPdf; pdf_sha256 = (Get-FileHash -LiteralPath $reportPdf -Algorithm SHA256).Hash.ToLower() } | ConvertTo-Json | Set-Content -LiteralPath $reportReceipt -Encoding utf8
  Write-Output "Exported formatted report PDF; pages=$reportPages"
} finally {
  if ($null -ne $reportDoc) { $reportDoc.Close(0); [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($reportDoc) | Out-Null }
  if ($null -ne $reportWord) { $reportWord.Quit(); [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($reportWord) | Out-Null }
}
