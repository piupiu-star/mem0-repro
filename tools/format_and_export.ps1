$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$docx = Join-Path $root 'REPORT.docx'
$pdf  = Join-Path $root 'REPORT.pdf'
$bak  = Join-Path $root 'REPORT_before_format.docx'

Copy-Item $docx $bak -Force
"backup -> $bak"

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$doc = $word.Documents.Open($docx, $false, $false)

# ---------- page setup: A4 ----------
$ps = $doc.PageSetup
$ps.PageWidth       = 595.3
$ps.PageHeight      = 841.9
$ps.LeftMargin      = 62.4
$ps.RightMargin     = 62.4
$ps.TopMargin       = 56.7
$ps.BottomMargin    = 56.7
$ps.HeaderDistance  = 28.3
$ps.FooterDistance  = 28.3
$ps.Gutter          = 0

# ---------- style helper ----------
function Set-Style($doc, [int]$id, [string]$ascii, [string]$ea, [double]$size, [int]$bold, [int]$italic,
                    [double]$before, [double]$after, [int]$align, [int]$keepNext) {
    try {
        $st = $doc.Styles.Item($id)
        $st.Font.NameAscii = $ascii
        $st.Font.NameFarEast = $ea
        $st.Font.NameOther = $ascii
        $st.Font.Size = $size
        $st.Font.Bold = $bold
        $st.Font.Italic = $italic
        $st.Font.ColorIndex = 0
        $pf = $st.ParagraphFormat
        $pf.SpaceBefore = $before
        $pf.SpaceAfter = $after
        $pf.LineSpacingRule = 0
        $pf.Alignment = $align
        $pf.KeepWithNext = $keepNext
        $pf.WidowControl = -1
        return "ok"
    } catch { return "ERR: $($_.Exception.Message)" }
}

$serif = "Times New Roman"
$cjk   = "SimSun"

# Normal body: 10.5pt, justified, single spacing
"Normal     : " + (Set-Style $doc -1   $serif $cjk 10.5 0 0 0   5 3 0)
"ListPara   : " + (Set-Style $doc -180 $serif $cjk 10.5 0 0 0   4 0 0)
"Title      : " + (Set-Style $doc -63  $serif $cjk 20   -1 0 0  12 1 0)
"Heading 1  : " + (Set-Style $doc -2   $serif $cjk 14   -1 0 14  6 0 -1)
"Heading 2  : " + (Set-Style $doc -3   $serif $cjk 12   -1 0 11  4 0 -1)
"Heading 3  : " + (Set-Style $doc -4   $serif $cjk 10.5 -1 1 9   3 0 -1)

# Heading 1 gets a hairline rule above it for a formal look
try {
    $h1 = $doc.Styles.Item(-2)
    $h1.ParagraphFormat.Borders.Item(-1).LineStyle = 1
    $h1.ParagraphFormat.Borders.Item(-1).LineWidth = 6
} catch {}

# ---------- tables ----------
$ti = 0
foreach ($t in $doc.Tables) {
    $ti++
    $t.Range.Font.Name = $serif
    $t.Range.Font.Size = 9
    $t.Range.ParagraphFormat.SpaceBefore = 1
    $t.Range.ParagraphFormat.SpaceAfter = 1
    $t.Range.ParagraphFormat.LineSpacingRule = 0
    $t.Rows.Alignment = 2
    try {
        $t.Rows.Item(1).HeadingFormat = $true
        $t.Rows.Item(1).Range.Font.Bold = $true
        $t.Rows.Item(1).Range.ParagraphFormat.Alignment = 1
    } catch {}
    $t.TopPadding = 2
    $t.BottomPadding = 2
    $t.LeftPadding = 4
    $t.RightPadding = 4
}
"tables styled: $ti"

# ---------- footer with page X of Y ----------
$sec = $doc.Sections.Item(1)
$f = $sec.Footers.Item(1)
$r = $f.Range
$r.Text = "FTEC5660 Reproducibility Study  |  Mem0  |  Xiuling PIAO 1155267871  |  Page "
$r = $f.Range
$r.Collapse(0)
$r.Fields.Add($r, 33) | Out-Null
$r = $f.Range
$r.Collapse(0)
$r.InsertAfter(" of ")
$r = $f.Range
$r.Collapse(0)
$r.Fields.Add($r, 26) | Out-Null
$f.Range.Font.Name = $serif
$f.Range.Font.Size = 9
$f.Range.ParagraphFormat.Alignment = 1
$f.Range.ParagraphFormat.SpaceBefore = 0
$f.Range.ParagraphFormat.SpaceAfter = 0

# ---------- metadata ----------
try { $doc.BuiltInDocumentProperties("Title").Value = "Reproducing Mem0 on LOCOMO" } catch {}
try { $doc.BuiltInDocumentProperties("Author").Value = "Xiuling PIAO (1155267871)" } catch {}
try { $doc.BuiltInDocumentProperties("Subject").Value = "FTEC5660 Reproducibility Work" } catch {}

$doc.Repaginate()
"pages after format : " + $doc.ComputeStatistics(2)
"words after format : " + $doc.ComputeStatistics(0)

$doc.Save()

# ---------- export ----------
if (Test-Path $pdf) { Remove-Item $pdf -Force }
$doc.ExportAsFixedFormat($pdf, 17, $false, 0, 0, 0, 0, 0, $true, $true, 1, $true, $true, $false)
"exported -> $pdf"

$doc.Close($false)
$word.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) | Out-Null
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
Get-Item $pdf | Select-Object Name, LastWriteTime, Length | Format-Table -AutoSize
