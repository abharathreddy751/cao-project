cd "D:/cao project"
for n in d1.0_dss2b_c56.7_24.0 d1.1_dss2b_c10.7_41.3 d1.5_dss2b_c56.7_24.0; do
  .venv/Scripts/python.exe scripts/montage_sequential.py --pin-lp 2 --instance $n --out data/results/stage3_20261012/refs/$n > data/results/stage3_20261012/refs/$n.stdout.txt 2>&1
done
echo ALLDONE > data/results/stage3_20261012/refs/DONE.txt
