"""Checks the program against tests/expected.py (in-game screenshots) and that
exports don't change unexpectedly.

    python3 tests/check_saves.py                    # compare with the screenshots
    python3 tests/check_saves.py --rom lazarus.sav=Lazarus.gba ...   # also use ROMs

Without ROMs, the items in NEEDS_ROM are reported as "needs ROM", not failures."""
import importlib.util, os, sys
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('php', os.path.join(here, '..', 'pokemon_hack_porter.py'))
php = importlib.util.module_from_spec(spec); spec.loader.exec_module(php)
sys.path.insert(0, here)
from expected import EXPECTED, NEEDS_ROM

roms = dict(a.split('=', 1) for a in sys.argv[1:] if '=' in a)
fails = 0
for save, mons in EXPECTED.items():
    pick = (lambda ps: next(p for p in ps if p.short == 'Gaia')) if save == 'gaia.sav' else None
    prof, trainer, raw = php.open_save(os.path.join(here, 'saves', save), pick)
    prof.rom = php.RomTables(roms[save], prof.needs_rom) if save in roms else None
    entries = {e.where: e for e in (php.Entry(w, p, m, prof) for w, p, m in raw)}
    print('==', save, '(%s)' % prof.name)
    for where, (species, level, sex, nature, moves, met, exp) in mons.items():
        e = entries.get(where)
        if e is None:
            print('  FAIL %s: not found' % where); fails += 1; continue
        got_sex = {0: 'M', 1: 'F', 2: '-'}.get(getattr(e, 'gender', None), '?')
        checks = {'species': (e.name, species), 'level': (e.level, level), 'gender': (got_sex, sex),
                  'nature': (php.NATURES[e.m['pid'] % 25], nature),
                  'moves': ([php.MOVES[x] for x in e.moves], moves), 'met level': (e.m['met_level'], met)}
        if exp is not None:
            checks['exp'] = (e.m['exp'], exp)
        bad = []
        for k, (got, want) in checks.items():
            if got != want:
                tag = 'needs ROM' if (save, where, k) in NEEDS_ROM and save not in roms else 'FAIL'
                bad.append('%s %s: got %r, game shows %r' % (tag, k, got, want))
                fails += tag == 'FAIL'
        print('  %-14s %-16s %s' % (where, species, '; '.join(bad) or 'ok'))
print('\n%d failure(s)' % fails)
sys.exit(1 if fails else 0)
