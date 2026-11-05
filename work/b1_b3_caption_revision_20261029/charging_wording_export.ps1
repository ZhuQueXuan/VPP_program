$ErrorActionPreference = 'Stop'
$wordingTargets = @(
  @{Input='D:\myDocu\project_postg\VPP_program\04_汇报与调研资料\课题一B1至B3算法阶段研究报告_20261029.docx'; Work='D:\myDocu\project_postg\VPP_program\work\b1_b3_caption_revision_20261029'},
  @{Input='D:\myDocu\project_postg\VPP_program\04_汇报与调研资料\课题一B1至B3算法汇报讲解稿_个人理解版_20261029.docx'; Work='D:\myDocu\project_postg\VPP_program\work\b123_personal_briefing_20261029'}
)
$wordingWord=$null
try {
  $wordingWord=New-Object -ComObject Word.Application
  $wordingWord.Visible=$false
  $wordingWord.DisplayAlerts=0
  foreach ($wordingTarget in $wordingTargets) {
    $wordingDoc=$null
    try {
      $wordingPdf=Join-Path $wordingTarget.Work 'charging_wording_preview.pdf'
      $wordingDoc=$wordingWord.Documents.Open($wordingTarget.Input,$false,$true)
      $wordingDoc.Repaginate()
      $wordingDoc.ExportAsFixedFormat($wordingPdf,17)
      $wordingPages=$wordingDoc.ComputeStatistics(2)
      @{status='success';renderer='Microsoft Word native PDF export';page_count=$wordingPages;input=$wordingTarget.Input;input_sha256=(Get-FileHash -LiteralPath $wordingTarget.Input -Algorithm SHA256).Hash.ToLower();pdf=$wordingPdf;pdf_sha256=(Get-FileHash -LiteralPath $wordingPdf -Algorithm SHA256).Hash.ToLower()} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $wordingTarget.Work 'charging_wording_export.json') -Encoding UTF8
      Write-Output "Preview exported; pages=$wordingPages"
    } finally {
      if ($null -ne $wordingDoc) {$wordingDoc.Close(0);[System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordingDoc)|Out-Null}
    }
  }
} finally {
  if ($null -ne $wordingWord) {$wordingWord.Quit();[System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordingWord)|Out-Null}
}
