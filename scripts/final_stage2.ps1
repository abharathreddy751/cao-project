# Final study stage 2: the six evaluation sessions in the registered order, each analysed once complete. Idempotent: a design whose session
# is already complete is not run again; an aborted attempt stays on disk and the design is retried under a new id (final_run_sessions.ps1).
#   .\scripts\final_stage2.ps1
# Stops (throws) at the first design that has no complete session, so a later design is never run on top of a failed earlier one.
param([string]$Root = "data\results\final_20261101", [string]$Log = "data\results\final_20261101\ACTIVITY_LOG.md")
Set-Location "D:\cao project"
function Log($m) { "$((Get-Date).ToUniversalTime().ToString('o'))  $m" | Out-File $Log -Append -Encoding utf8 }
$order = "eval_h16_l120", "eval_uniform", "eval_h04_l120", "eval_h40_l120", "eval_h16_l40", "eval_h16_l15"
$eval = "$Root\eval"
function CompleteSession($d) {
    Get-ChildItem "$eval\sessions" -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq $d -or $_.Name -like "${d}_r*" } | Where-Object {
        $j = "$($_.FullName)\session.json"; (Test-Path $j) -and ((Get-Content $j -Raw | ConvertFrom-Json).status -eq "complete") } | Select-Object -First 1
}
foreach ($d in $order) {
    $wl = $d.Substring(5)
    $done = CompleteSession $d
    if (-not $done) {
        & .\scripts\final_run_sessions.ps1 -Dir $eval -Designs $d
        $done = CompleteSession $d
    }
    if (-not $done) { Log "STAGE2 STOPPED: no complete session for $d"; throw "no complete session for $d" }
    $out = "$eval\analysis_$wl"
    if (-not (Test-Path $out)) {
        $extra = @(if ($d -eq "eval_h16_l120") { "--confirmatory" })   # @() keeps it an array: a bare string would be splatted per character
        & .\.venv\Scripts\python.exe scripts\final_analyze.py --session $done.FullName --out $out @extra *>> "$eval\analyze_$wl.stdout.txt"
        Log "analysed $d -> $out (exit $LASTEXITCODE) session $($done.Name)"
    }
}
Log "STAGE2 COMPLETE: all six evaluation sessions complete and analysed"
"STAGE2_DONE" | Out-File "$Root\STAGE2_DONE.txt" -Encoding utf8
