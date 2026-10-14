cd "D:/cao project"
out=data/results/stage1_20261011/tests/suite_by_file_$(date +%Y%m%dT%H%M%S).txt
for f in tests/test_*.py; do
  s=$(date +%s)
  r=$(timeout 900 .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider "$f" 2>&1 | tail -3 | tr '\n' ' ')
  echo "$f rc=$? $(( $(date +%s)-s ))s :: $r" >> "$out"
done
echo DONE >> "$out"
