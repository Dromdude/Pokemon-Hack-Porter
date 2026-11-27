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
for f in os.listdir(tmp):
    os.remove(os.path.join(tmp, f))
os.rmdir(tmp)
print('\n%d failure(s)' % fails)
sys.exit(1 if fails else 0)
