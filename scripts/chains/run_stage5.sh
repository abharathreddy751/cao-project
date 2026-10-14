cd "D:/cao project"
S=data/results/stage5_20261013
.venv/Scripts/python.exe scripts/load_monitor.py $S/load/load_$(date +%Y%m%dT%H%M%S).jsonl --interval 30 > /dev/null 2>&1 &
MON=$!
CAO_GPU_ADAPTER_CONFIG="D:/cao project/$S/designs/gpu/adapter_config_gpu.json" .venv/Scripts/python.exe scripts/run_experiment.py --design $S/designs/gpu/design_gpu_confirm.json --out $S/gpu_sessions --adapter caosched.experiment.gpu_adapter:factory > $S/gpu.stdout.txt 2>&1
echo "gpu rc=$?" >> $S/progress.txt
CAO_MONTAGE_ADAPTER_CONFIG="D:/cao project/$S/designs/adapter_config_main.json" .venv/Scripts/python.exe scripts/run_experiment.py --design $S/designs/design_main_confirm.json --out $S/sessions_main --adapter caosched.experiment.montage_adapter:factory > $S/main.stdout.txt 2>&1
echo "main rc=$?" >> $S/progress.txt
CAO_MONTAGE_ADAPTER_CONFIG="D:/cao project/$S/designs/adapter_config_regimeR.json" .venv/Scripts/python.exe scripts/run_experiment.py --design $S/designs/design_regimeR_confirm.json --out $S/sessions_regimeR --adapter caosched.experiment.montage_adapter:factory > $S/regimeR.stdout.txt 2>&1
echo "regimeR rc=$?" >> $S/progress.txt
kill $MON 2>/dev/null
echo ALLDONE >> $S/progress.txt
