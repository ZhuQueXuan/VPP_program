$ErrorActionPreference='Stop'
$headingBase='D:\myDocu\project_postg\VPP_program\work\b1_b3_caption_revision_20261029'
$headingInput=Join-Path $headingBase 'heading_numbering_staged.docx'
$headingPdf=Join-Path $headingBase 'heading_numbering_preview.pdf'
$headingWord=$null
$headingDoc=$null
try {
  $headingWord=New-Object -ComObject Word.Application
  $headingWord.Visible=$false
  $headingWord.DisplayAlerts=0
  $headingDoc=$headingWord.Documents.Open($headingInput,$false,$true)
  $headingDoc.Repaginate()
  $headingDoc.ExportAsFixedFormat($headingPdf,17)
  @{status='success';renderer='Microsoft Word native PDF export';page_count=$headingDoc.ComputeStatistics(2);input=$headingInput;input_sha256=(Get-FileHash -LiteralPath $headingInput -Algorithm SHA256).Hash.ToLower();pdf=$headingPdf;pdf_sha256=(Get-FileHash -LiteralPath $headingPdf -Algorithm SHA256).Hash.ToLower()} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $headingBase 'heading_export.json') -Encoding UTF8
  Get-Content -LiteralPath (Join-Path $headingBase 'heading_export.json') -Raw
} finally {
  if($null -ne $headingDoc){$headingDoc.Close(0);[System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($headingDoc)|Out-Null}
  if($null -ne $headingWord){$headingWord.Quit();[System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($headingWord)|Out-Null}
}
