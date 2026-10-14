cd "D:/cao project"
S=data/results/stage3_20261012
for n in d1.0_dss2b_c56.7_24.0 d1.1_dss2b_c56.7_24.0 d1.1_dss2b_c10.7_41.3 d1.5_dss2b_c56.7_24.0; do
  out=$S/sessions; [ "$n" = "d1.5_dss2b_c56.7_24.0" ] && out=$S/sessions_test
  CAO_MONTAGE_ADAPTER_CONFIG="D:/cao project/$S/designs_v2/adapter_config_$n.json" .venv/Scripts/python.exe scripts/run_experiment.py --design $S/designs_v2/design_$n.json --out $out --adapter caosched.experiment.montage_adapter:factory > $S/collect_$n.stdout.txt 2>&1
  echo "$n rc=$?" >> $S/collect_progress.txt
done
echo ALLDONE >> $S/collect_progress.txt
