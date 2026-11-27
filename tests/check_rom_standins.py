"""Checks Load ROM against stand-in ROMs (tools/make_standin_roms.py): each layout
must be found and give the in-game results from tests/expected.py.
    python3 tests/check_rom_standins.py"""
import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
root = os.path.join(here, '..')
tmp = tempfile.mkdtemp()
subprocess.run([sys.executable, '-I', os.path.join(root, 'tools', 'make_standin_roms.py')], cwd=tmp, check=True)
cases = [('standin_expansion.gba', 'lazarus.sav'), ('standin_lazarus.gba', 'lazarus.sav')]
fails = 0
for rom, save in cases:
    print('== %s with %s' % (rom, save))
    r = subprocess.run([sys.executable, os.path.join(here, 'check_saves.py'), '--only', save,
                        '%s=%s' % (save, os.path.join(tmp, rom))], capture_output=True, text=True)
    print(r.stdout.strip().split('\n')[-1])
    if r.returncode:
        print(r.stdout); fails += 1
# The real Lazarus v2.0 ROM read by 1.1.3's _find_lazarus (tools/rom_data_export.py output):
# mostly misread, so the safety check must reject it.
import importlib.util
spec = importlib.util.spec_from_file_location('php', os.path.join(root, 'pokemon_hack_porter.py'))
php = importlib.util.module_from_spec(spec); spec.loader.exec_module(php)
rows = [l.split(',') for l in open(os.path.join(here, 'data', 'lazarus_v2.0_misread_romdata.csv'))
        if l[0].isdigit()]
agree, total = php.stats_agreement({int(r[0]): (int(r[2]), int(r[3])) for r in rows})
ok = agree < 0.75 * total
print('== misread Lazarus data: %d of %d agree -> %s' % (agree, total, 'rejected (ok)' if ok else 'ACCEPTED (FAIL)'))
fails += not ok
for f in os.listdir(tmp):
    os.remove(os.path.join(tmp, f))
os.rmdir(tmp)
print('\n%d failure(s)' % fails)
sys.exit(1 if fails else 0)
