cd "D:/cao project"
S=data/results/stage4_20261012
CAO_MONTAGE_ADAPTER_CONFIG="D:/cao project/$S/designs/adapter_config_main.json" .venv/Scripts/python.exe scripts/run_experiment.py --design $S/designs/design_main.json --out $S/sessions_main --adapter caosched.experiment.montage_adapter:factory > $S/main.stdout.txt 2>&1
echo "main rc=$?" >> $S/progress.txt
CAO_MONTAGE_ADAPTER_CONFIG="D:/cao project/$S/designs/adapter_config_regimeR.json" .venv/Scripts/python.exe scripts/run_experiment.py --design $S/designs/design_regimeR.json --out $S/sessions_regimeR --adapter caosched.experiment.montage_adapter:factory > $S/regimeR.stdout.txt 2>&1
echo "regimeR rc=$?" >> $S/progress.txt
echo ALLDONE >> $S/progress.txt
