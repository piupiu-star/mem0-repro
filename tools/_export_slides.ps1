# Export every slide to PNG so the layout can be eyeballed without opening PowerPoint.
$root = Split-Path -Parent $PSScriptRoot
$pptx = Join-Path $root 'slides\Mem0_Reproduction.pptx'
$out  = Join-Path $root 'slides\png'
if (-not (Test-Path $out)) { New-Item -ItemType Directory -Path $out | Out-Null }

$ppt = New-Object -ComObject PowerPoint.Application
$ppt.Visible = $true
$pres = $ppt.Presentations.Open($pptx, $true, $false, $false)

$i = 1
foreach ($s in $pres.Slides) {
    $f = Join-Path $out ('slide{0:d2}.png' -f $i)
    $s.Export($f, 'PNG', 1600, 900)
    $i++
}
"exported {0} slides" -f ($i - 1)

$pres.Close()
$ppt.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($pres) | Out-Null
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt) | Out-Null
[GC]::Collect()
Get-ChildItem $out -Filter *.png | Select-Object Name, Length | Format-Table -AutoSize
