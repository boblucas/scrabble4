#!/bin/bash
# One-shot validation of the xfill --batchvec engine + certifier v2, then (if green) launch the
# definitive floor-216 N=11 certification build in the background.
set -u
cd /home/bob/programming/scrabble4
PY=.venv/bin/python

echo "===== 1. build ====="
cargo build --release --manifest-path experiments/xfill_rs/Cargo.toml 2>&1 | grep -aE "^error|Finished" | head
$PY -m py_compile experiments/35_certify.py experiments/xtest.py && echo "python OK" || exit 1

echo "===== 2. soundness gates (legacy single-instance path must be byte-identical) ====="
bash experiments/regress.sh experiments/xfill_rs/target/release/xfill | tail -4 || exit 1

echo "===== 3. batchvec smoke: known vectors through the base path ====="
$PY - <<'PY'
import sys, subprocess, os
sys.path.insert(0,'.'); sys.path.insert(0,'experiments')
import xtest
os.makedirs('experiments/results/certs/smoke', exist_ok=True)
xtest.write_dict('11')
xtest.dump_base(xtest.build_base('11','bouwfysicus','BOUWfYsiCuS', scale=True),
                'experiments/results/certs/smoke/base.txt')
with open('experiments/results/certs/smoke/t.list','w') as f:
    # witness vector at floor 215 (expect MAX 216) and at floor 216 (expect LE 216);
    # deep-col10 vector at floor 224 (expect LE 224, the gate family)
    f.write("w215 11 3 2 7 3 5 11 215\n")
    f.write("w216 11 3 2 7 3 5 11 216\n")
    f.write("d224 11 3 2 7 3 5 10 224\n")
env = dict(os.environ); env['BATCHWALL']='240'
r = subprocess.run(['experiments/xfill_rs/target/release/xfill','--batchvec',
                    'experiments/results/certs/smoke/base.txt',
                    'experiments/results/certs/smoke/t.list'],
                   capture_output=True, text=True, env=env, timeout=900)
print(r.stdout.strip())
ok = ('RES w215 MAX 216' in r.stdout) and ('RES w216 LE 216' in r.stdout)
print('SMOKE', 'OK' if ok else 'FAIL  (stderr tail: %s)' % (r.stderr or '')[-300:])
sys.exit(0 if ok else 1)
PY
[ $? -eq 0 ] || exit 1

echo "===== 4. launch the definitive floor-216 certification build (background) ====="
setsid nohup $PY -u experiments/35_certify.py build --board 11 --main bouwfysicus \
  --turn BOUWfYsiCuS --floor 216 --name n11_fixed_216 --procs 12 --wall 600 \
  --witness experiments/results/certs/witness_n11_unconstrained_850.json \
  > experiments/results/certs/n11_fixed_216.log 2>&1 < /dev/null &
echo "launched: experiments/results/certs/n11_fixed_216.log"
sleep 20
tail -5 experiments/results/certs/n11_fixed_216.log
