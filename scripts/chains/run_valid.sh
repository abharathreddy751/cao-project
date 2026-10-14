cd "D:/cao project"
for r in 1 2 3; do
  .venv/Scripts/python.exe scripts/montage_sequential.py --pin-lp 2 --instance d1.1_dss2b_c56.7_24.0 --out data/results/stage1_20261011/valid/seq$r > data/results/stage1_20261011/valid/seq$r.stdout.txt 2>&1
done
echo finished
