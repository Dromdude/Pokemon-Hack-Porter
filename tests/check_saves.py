"""Checks the program against tests/expected.py (in-game screenshots) and that
exports don't change unexpectedly.

    python3 tests/check_saves.py                    # compare with the screenshots
    python3 tests/check_saves.py lazarus.sav=Lazarus.gba ...   # also use ROMs
    python3 tests/check_saves.py --only lazarus.sav           # one save

Without ROMs, the items in NEEDS_ROM are reported as "needs ROM", not failures."""
import importlib.util, os, sys
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('php', os.path.join(here, '..', 'pokemon_hack_porter.py'))
php = importlib.util.module_from_spec(spec); spec.loader.exec_module(php)
sys.path.insert(0, here)
from expected import EXPECTED, NEEDS_ROM

roms = dict(a.split('=', 1) for a in sys.argv[1:] if '=' in a)
only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
fails = 0
for save, mons in EXPECTED.items():
    if only and save != only:
        continue
    pick = (lambda ps: next(p for p in ps if p.short == 'Gaia')) if save == 'gaia.sav' else None
    prof, trainer, raw = php.open_save(os.path.join(here, 'saves', save), pick)
    prof.rom = php.RomTables(roms[save], prof.needs_rom) if save in roms else None
    if prof.rom:
        print('   ', prof.rom.summary, '| search:', '; '.join(php.STATS_DIAG[-2:]))
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
# Manual gender / level switches (what the window's ♂/♀ and Lv clicks do)
print('== manual switches')
for save, where, gender, level, want in (
        ('lazarus.sav', 'Party 4', 1, None, ('F', 14)),          # Fennekin: female in-game
        ('lazarus.sav', 'Party 3', 0, None, ('M', 13)),          # Mareep flipped to male (pk3 PID re-roll)
        ('light_platinum.sav', 'BOX1, slot 2', None, 5, ('M', 5))):  # Bidoof: Lv 5 in-game
    if only and save != only:
        continue
    pick = None
    prof, trainer, raw = php.open_save(os.path.join(here, 'saves', save), pick)
    prof.rom = None
    e = next(php.Entry(w, p, m, prof, False, gender, level) for w, p, m in raw if w == where)
    data = e.build()
    got = ({0: 'M', 1: 'F'}[e.gender], e.level)
    if e.format == 3:   # gender in a .pk3 comes from the personality value
        pid = int.from_bytes(data[0:4], 'little')
        got = ({0: 'M', 1: 'F'}[php.gender_from_ratio(pid, php.UU[e.nat][0])], e.level)
        assert pid % 25 == e.m['pid'] % 25, 'nature changed'
    good = got == want and php.level_for_exp(php.base_data(e.nat, e.form, e.format)[1] if e.format != 3
                                             else php.G3GROW[e.nat], e.exp) == want[1]
    print('  %-12s %-14s %s' % (save, where, 'ok' if good else 'FAIL got %r want %r' % (got, want)))
    fails += not good
print('\n%d failure(s)' % fails)
sys.exit(1 if fails else 0)
