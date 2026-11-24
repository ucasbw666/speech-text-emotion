param([string]$Root='D:\语音大作业')
$ErrorActionPreference = 'Stop'
$stem = '语音文字与情绪联合识别项目总结与交接报告'
$docxPath = Join-Path $Root ('交接报告\' + $stem + '.docx')
$pdfPath = Join-Path $Root ('交接报告\' + $stem + '.pdf')
$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $document = $word.Documents.Open($docxPath,$false,$true)
    $document.ExportAsFixedFormat($pdfPath,17)
    Write-Output $pdfPath
} finally {
    if ($null -ne $document) { $document.Close(0); [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($document) }
    if ($null -ne $word) { $word.Quit(0); [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) }
}
