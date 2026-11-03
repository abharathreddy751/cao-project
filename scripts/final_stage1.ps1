# Final study, stage 1: calibration sessions -> model, e2e terms, evaluation designs, oracle rows, smoke session. Stops at the first failed gate.
Set-Location "D:\cao project"
$F = "data\results\final_20261101"
$PY = ".\.venv\Scripts\python.exe"
$Log = "$F\ACTIVITY_LOG.md"
function Log($m) { "$((Get-Date).ToUniversalTime().ToString('o'))  $m" | Out-File $Log -Append -Encoding utf8 }
function Pick($dir, $d) {   # the complete session of a design (first complete among d, d_r2, ...)
    foreach ($s in (Get-ChildItem "$dir\sessions" -Directory -Filter "$d*" -ErrorAction SilentlyContinue | Sort-Object Name)) {
        $sj = Join-Path $s.FullName "session.json"
        if ((Test-Path $sj) -and ((Get-Content $sj -Raw | ConvertFrom-Json).status -eq "complete")) { return $s.FullName }
    }
    return $null
}
function Stop-Stage($m) { Log "STAGE1 STOPPED: $m"; throw $m }

# 1. calibration + hold-out sessions
$cal = @("cal_l120", "cal_l40", "cal_l15", "cal_uniform", "hold_l120", "hold_l40")
$todo = $cal | Where-Object { -not (Pick "$F\calibration" $_) }
if ($todo) { & .\scripts\final_run_sessions.ps1 -Dir "$F\calibration" -Designs ($todo -join ",") }
$sess = @{}
foreach ($d in $cal) { $p = Pick "$F\calibration" $d; if (-not $p) { Stop-Stage "calibration session $d not complete" }; $sess[$d] = $p }
Log "calibration sessions complete: $(($sess.GetEnumerator() | ForEach-Object { $_.Value }) -join '; ')"

# 2. model, e2e terms (training sessions only), hold-out report
New-Item -ItemType Directory -Force -Path "$F\models" | Out-Null
$train = @($sess.cal_l15, $sess.cal_l40, $sess.cal_l120, $sess.cal_uniform)
$pm = "$F\models\param_model_final.json"; $terms = "$F\models\e2e_terms_final.json"
if (-not (Test-Path $pm)) { & $PY scripts\study2_train_param_model.py $pm @train --holdout $sess.hold_l40 $sess.hold_l120 *>> "$F\models\train.stdout.txt"; if ($LASTEXITCODE -ne 0) { Stop-Stage "model training failed" } }
if (-not (Test-Path $terms)) { & $PY scripts\study2_e2e_terms.py $terms @train *>> "$F\models\e2e.stdout.txt"; if ($LASTEXITCODE -ne 0) { Stop-Stage "e2e terms failed" } }
Log "model $((Get-FileHash $pm -Algorithm SHA256).Hash) terms $((Get-FileHash $terms -Algorithm SHA256).Hash)"

# 3. evaluation designs (+ smoke copy), oracle rows
New-Item -ItemType Directory -Force -Path "$F\eval\designs", "$F\eval\oracle" | Out-Null
if (-not (Test-Path "$F\eval\designs\design_final_eval_h16_l120.json")) {
    & $PY scripts\final_make_designs.py evaluation "$F\eval\designs" $pm $terms "$F\eval\oracle" *>> "$F\eval\make_designs.stdout.txt"
    if ($LASTEXITCODE -ne 0) { Stop-Stage "design generation failed" }
}
foreach ($dn in Get-ChildItem "$F\eval\designs" -Filter "design_final_eval_*.json") {
    & $PY scripts\final_oracle_rows.py $dn.FullName @train *>> "$F\eval\oracle_rows.stdout.txt"
    if ($LASTEXITCODE -ne 0) { Stop-Stage "oracle rows failed for $($dn.Name) (see eval\oracle_rows.stdout.txt)" }
}
if (-not (Test-Path "$F\eval\designs\design_final_smoke.json")) {
    & $PY -c "import json,sys; d=json.load(open(r'$F\eval\designs\design_final_eval_h16_l120.json')); d.update(name='final_smoke', n_blocks=2, seed=20261199); open(r'$F\eval\designs\design_final_smoke.json','x').write(json.dumps(d,indent=1))"
}
Get-ChildItem "$F\eval\designs" | ForEach-Object { "{0}  {1}" -f (Get-FileHash $_.FullName -Algorithm SHA256).Hash, $_.Name } | Out-File "$F\eval\designs_sha256.txt" -Encoding utf8
Log "evaluation designs written; hashes in eval\designs_sha256.txt; protocol sha256 $((Get-FileHash docs\final\PROTOCOL_final.md -Algorithm SHA256).Hash)"

# 4. smoke session (2 blocks of the primary design): every condition must run and verify
if (-not (Pick "$F\eval" "smoke")) { & .\scripts\final_run_sessions.ps1 -Dir "$F\eval" -Designs "smoke" -Prefix "design_final_" }
$sm = Pick "$F\eval" "smoke"
if (-not $sm) { Stop-Stage "smoke session not complete" }
$bad = & $PY -c "import json,glob; b=[(json.load(open(p))['condition']['name'],json.load(open(p))['status'],json.load(open(p))['verification']['passed']) for p in glob.glob(r'$sm\runs\*\run_manifest.json')]; b=[x for x in b if x[1]!='ok' or x[2] is not True]; print(len(b)); print(b[:10])"
Log "smoke session $sm : runs not ok/verified: $bad"
if ($bad[0] -ne "0") { Stop-Stage "smoke has failed runs: $bad" }
Log "STAGE1 COMPLETE"
"STAGE1 COMPLETE" | Out-File "$F\STAGE1_DONE.txt" -Encoding utf8
