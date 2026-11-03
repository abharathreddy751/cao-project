# Run registered designs one after another (final study). Each session is written to a NEW directory; nothing is overwritten.
#   .\scripts\final_run_sessions.ps1 -Dir data\results\final_20261101\calibration -Designs cal_l120,cal_l40
# The machine's free RAM can fall below what a session needs (an unrelated service holds several GB): before every attempt this script waits
# until free RAM >= -StartGB (default 2.4: a session start at 4.15 GB free had 2.78 GB left once the worker pool was alive, i.e. the pool and run cost about 1.4 GB, and the block rule needs 0.8 GB left). The design's own rule
# (min_free_ram_gb per block) is NOT lowered. An attempt that is aborted or crashed stays on disk as evidence of that and the design is
# run again under a new session id (<design>_r2, _r3, ...); the analysis accepts only 'complete' sessions.
param(
    [Parameter(Mandatory = $true)][string]$Dir,
    [Parameter(Mandatory = $true)][string[]]$Designs,
    [string]$Prefix = "design_final_",
    [double]$StartGB = 2.4,
    [int]$MaxTries = 4,
    [int]$WaitMinutes = 600,
    [string]$Log = "data\results\final_20261101\ACTIVITY_LOG.md"
)
Set-Location "D:\cao project"
$Designs = @($Designs | ForEach-Object { $_ -split "," } | Where-Object { $_ })
$env:CAO_FINAL_ADAPTER_CONFIG = (Resolve-Path "data\results\final_20261101\adapter_config_final.json").Path
function Log($m) { "$((Get-Date).ToUniversalTime().ToString('o'))  $m" | Out-File $Log -Append -Encoding utf8 }
function FreeGB { [double](& .\.venv\Scripts\python.exe -c "import psutil;print(round(psutil.virtual_memory().available/2**30,2))") }
# The designs set require_ac_power: a session started on battery aborts at once. Wait for mains too (the design rule itself is unchanged).
Add-Type -AssemblyName System.Windows.Forms
function OnAC { [System.Windows.Forms.SystemInformation]::PowerStatus.PowerLineStatus -eq "Online" }
foreach ($d in $Designs) {
    $design = "$Dir\designs\$Prefix$d.json"
    $stdout = "$Dir\run_$d.stdout.txt"
    $done = $false
    for ($try = 1; $try -le $MaxTries -and -not $done; $try++) {
        # first unused id: earlier (aborted) attempts stay on disk and are never reused
        $n = 1; while (Test-Path "$Dir\sessions\$(if ($n -eq 1) { $d } else { "${d}_r$n" })") { $n++ }
        $sid = if ($n -eq 1) { $d } else { "${d}_r$n" }
        $deadline = (Get-Date).AddMinutes($WaitMinutes); $ok = 0
        while ((Get-Date) -lt $deadline -and $ok -lt 3) { if ((FreeGB) -ge $StartGB -and (OnAC)) { $ok++ } else { $ok = 0 }; Start-Sleep -Seconds 20 }
        if ($ok -lt 3) { Log "$sid memory >= $StartGB GB and mains power not reached within $WaitMinutes min; giving up on this design"; break }
        Log "START $sid design sha256 $((Get-FileHash $design -Algorithm SHA256).Hash) free $(FreeGB) GB"
        & .\.venv\Scripts\python.exe scripts\run_experiment.py --design $design --out "$Dir\sessions" --adapter caosched.final.adapter:factory --session-id $sid *>> $stdout
        $rc = $LASTEXITCODE
        "exit=$rc" | Out-File $stdout -Append -Encoding utf8
        $sj = "$Dir\sessions\$sid\session.json"
        $status = if (Test-Path $sj) { (Get-Content $sj -Raw | ConvertFrom-Json).status } else { "no session.json" }
        Log "FINISHED $sid exit=$rc status=$status"
        if ($status -eq "complete") { $done = $true }
    }
    if (-not $done) { Log "NOT COMPLETE: $d" }
}
Log "ALLDONE $($Designs -join ',')"
"ALLDONE" | Out-File "$Dir\ALLDONE_$($Designs[0]).txt" -Encoding utf8

