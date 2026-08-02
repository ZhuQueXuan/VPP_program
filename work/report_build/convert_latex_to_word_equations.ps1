param(
  [string]$InputDoc = "",
  [string]$OutputDoc = ""
)

$ErrorActionPreference = "Stop"

$root = (Get-Location).Path

if ([string]::IsNullOrWhiteSpace($InputDoc)) {
  $reportsDir = Join-Path $root "outputs\reports"
  $inputItem = Get-ChildItem -LiteralPath $reportsDir -Filter "*LaTeX*.docx" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
  if ($null -eq $inputItem) {
    throw "No input DOCX matching *LaTeX*.docx was found in outputs\reports."
  }
  $inputPath = $inputItem.FullName
}
else {
  $inputPath = (Get-Item -LiteralPath (Join-Path $root $InputDoc)).FullName
}

if ([string]::IsNullOrWhiteSpace($OutputDoc)) {
  $outputPath = Join-Path (Split-Path -Parent $inputPath) "topic1-v1-word-equations-temp.docx"
}
else {
  $outputPath = Join-Path $root $OutputDoc
}

if (-not (Test-Path -LiteralPath $inputPath)) {
  throw "Input document not found: $inputPath"
}

$word = $null
$doc = $null

function Convert-RangeToEquation {
  param(
    [object]$Document,
    [int]$Start,
    [int]$End,
    [string]$Formula
  )

  $linearFormula = Convert-LatexToUnicodeMath $Formula
  $range = $Document.Range($Start, $End)
  $range.Text = $linearFormula
  $mathRange = $Document.Range($Start, $Start + $linearFormula.Length)
  $maths = $Document.OMaths.Add($mathRange)
  for ($k = 1; $k -le $maths.Count; $k++) {
    $maths.Item($k).BuildUp()
  }
}

function Convert-LatexToUnicodeMath {
  param([string]$Formula)

  $s = $Formula
  $s = $s -replace "\\left", ""
  $s = $s -replace "\\right", ""
  $s = $s -replace "\\times", "×"
  $s = $s -replace "\\Phi", "Φ"
  $s = $s -replace "\\tau", "τ"
  $s = $s -replace "\\quad", " "
  $s = $s -replace "\\,", " "
  $s = $s -replace "\\ ", " "
  $s = [System.Text.RegularExpressions.Regex]::Replace($s, "\\mathrm\{([^}]*)\}", '$1')
  $s = [System.Text.RegularExpressions.Regex]::Replace($s, "_\{([^}]*)\}", '_($1)')
  $s = [System.Text.RegularExpressions.Regex]::Replace($s, "\^\{([^}]*)\}", '^($1)')
  $s = $s -replace "\\", ""
  $s = $s -replace "\s+", " "
  return $s.Trim()
}

try {
  $word = New-Object -ComObject Word.Application
  $word.Visible = $false
  $word.DisplayAlerts = 0

  $doc = $word.Documents.Open($inputPath)

  # Convert display equations in paragraphs that are exactly \[...\].
  for ($i = $doc.Paragraphs.Count; $i -ge 1; $i--) {
    $paragraph = $doc.Paragraphs.Item($i)
    $text = $paragraph.Range.Text
    $clean = $text.Trim()
    if ($clean.StartsWith("\[") -and $clean.EndsWith("\]")) {
      $formula = $clean.Substring(2, $clean.Length - 4).Trim()
      $range = $paragraph.Range
      $start = $range.Start
      $end = $range.End - 1
      Convert-RangeToEquation -Document $doc -Start $start -End $end -Formula $formula
    }
  }

  # Convert inline equations \(...\), scanning from the end so offsets remain stable.
  for ($i = $doc.Paragraphs.Count; $i -ge 1; $i--) {
    $paragraph = $doc.Paragraphs.Item($i)
    $text = $paragraph.Range.Text
    $matches = [System.Text.RegularExpressions.Regex]::Matches($text, "\\\((.+?)\\\)")
    for ($j = $matches.Count - 1; $j -ge 0; $j--) {
      $m = $matches.Item($j)
      $formula = $m.Groups.Item(1).Value.Trim()
      if ($formula.Length -gt 0) {
        $start = $paragraph.Range.Start + $m.Index
        $end = $start + $m.Length
        Convert-RangeToEquation -Document $doc -Start $start -End $end -Formula $formula
      }
    }
  }

  $savePath = [string]$outputPath
  $doc.SaveAs2($savePath)
  $doc.Close([ref]$false)
  $word.Quit()

  Write-Output $outputPath
}
finally {
  if ($doc -ne $null) {
    try { $doc.Close([ref]$false) | Out-Null } catch {}
  }
  if ($word -ne $null) {
    try { $word.Quit() | Out-Null } catch {}
  }
}
