$ErrorActionPreference = 'Stop'
$path = (Resolve-Path (Join-Path $PSScriptRoot '..\REPORT.docx')).Path
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$doc = $word.Documents.Open($path, $false, $true)

"--- builtin style fonts ---"
$map = @{ 'Normal' = -1; 'Heading1' = -2; 'Heading2' = -3; 'Heading3' = -4; 'Title' = -63; 'ListParagraph' = -180 }
foreach ($k in $map.Keys) {
    try {
        $st = $doc.Styles.Item($map[$k])
        "{0,-14} name={1,-20} farEast={2,-14} size={3,-5} bold={4,-5} spaceBef={5,-5} spaceAft={6,-5} lineRule={7}" -f `
            $k, $st.Font.Name, $st.Font.NameFarEast, $st.Font.Size, $st.Font.Bold, `
            $st.ParagraphFormat.SpaceBefore, $st.ParagraphFormat.SpaceAfter, $st.ParagraphFormat.LineSpacingRule
    } catch { "$k : ERROR $($_.Exception.Message)" }
}

"--- sections ---"
"section count: " + $doc.Sections.Count
$sec = $doc.Sections.Item(1)
"footer text: [" + ($sec.Footers.Item(1).Range.Text -replace "[\r\n\a]", "") + "]"
"footer fields: " + $sec.Footers.Item(1).Range.Fields.Count
"header text: [" + ($sec.Headers.Item(1).Range.Text -replace "[\r\n\a]", "") + "]"

"--- first table ---"
$t = $doc.Tables.Item(1)
"table style: " + $t.Style.NameLocal
"table font size: " + $t.Range.Font.Size
"table font name: " + $t.Range.Font.Name
"rows: " + $t.Rows.Count + "  cols: " + $t.Columns.Count

"--- body sample run fonts (first 5 non-empty paragraphs with 30+ chars) ---"
$n = 0
foreach ($p in $doc.Paragraphs) {
    $txt = ($p.Range.Text -replace "[\r\n\a]", "").Trim()
    if ($txt.Length -ge 30) {
        "{0,-10} size={1,-5} name={2,-18} bold={3} | {4}" -f $p.Style.NameLocal, $p.Range.Font.Size, $p.Range.Font.Name, $p.Range.Font.Bold, $txt.Substring(0, 45)
        $n++
        if ($n -ge 5) { break }
    }
}

"--- last page fill ---"
$last = $doc.Content
$last.Collapse(0)
$pnum = $last.Information(3)
$pos = $last.Information(6)
$usable = $doc.PageSetup.PageHeight - $doc.PageSetup.TopMargin - $doc.PageSetup.BottomMargin
"last page: {0}  vertical pos: {1:N1} of {2:N1} pt ({3:N0}%)" -f $pnum, $pos, $usable, (100 * $pos / $usable)

$doc.Close($false)
$word.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) | Out-Null
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
