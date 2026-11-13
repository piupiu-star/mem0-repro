$ErrorActionPreference = 'Stop'
$path = Join-Path $PSScriptRoot '..\REPORT.docx'
$path = (Resolve-Path $path).Path
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$doc = $word.Documents.Open($path, $false, $true)
"pages : " + $doc.ComputeStatistics(2)
"words : " + $doc.ComputeStatistics(0)
"chars : " + $doc.ComputeStatistics(3)
"tables: " + $doc.Tables.Count
"inline shapes: " + $doc.InlineShapes.Count
"hyperlinks: " + $doc.Hyperlinks.Count
$ps = $doc.PageSetup
"page  : {0} x {1} pt" -f [math]::Round($ps.PageWidth,1), [math]::Round($ps.PageHeight,1)
"margin: L={0} R={1} T={2} B={3} Gutter={4}" -f [math]::Round($ps.LeftMargin,1), [math]::Round($ps.RightMargin,1), [math]::Round($ps.TopMargin,1), [math]::Round($ps.BottomMargin,1), [math]::Round($ps.Gutter,1)
"--- paragraph styles in use ---"
$seen = @{}
foreach ($p in $doc.Paragraphs) {
    $s = $p.Style.NameLocal
    if ($seen.ContainsKey($s)) { $seen[$s] = $seen[$s] + 1 } else { $seen[$s] = 1 }
}
$seen.GetEnumerator() | Sort-Object Value -Descending | ForEach-Object { "{0,-24} {1,4}" -f $_.Key, $_.Value }
"--- key style fonts ---"
foreach ($n in @("Normal","Heading 1","Heading 2","Heading 3","Title","List Number","List Bullet")) {
    try {
        $st = $doc.Styles.Item($n)
        "{0,-14} font={1,-18} size={2,-5} bold={3}" -f $n, $st.Font.Name, $st.Font.Size, $st.Font.Bold
    } catch { "$n : <missing>" }
}
"--- first 12 paragraph previews ---"
$i = 0
foreach ($p in $doc.Paragraphs) {
    $t = $p.Range.Text
    $t = $t -replace "[\r\n\a]", " "
    if ($t.Trim().Length -gt 0) {
        "{0,3} [{1,-14}] {2}" -f $i, $p.Style.NameLocal, $t.Substring(0, [Math]::Min(70, $t.Length))
    }
    $i = $i + 1
    if ($i -ge 12) { break }
}
$doc.Close($false)
$word.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) | Out-Null
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
