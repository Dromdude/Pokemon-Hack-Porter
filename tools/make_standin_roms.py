"""Stand-in ROMs for testing Load ROM without real ROMs. They contain no game data:
random bytes plus a species table (base stats, gender ratio, growth rate) built from
official values, laid out like each hack family's table, with changes seen in-game.
Run from the repository root:  python3 tools/make_standin_roms.py  (writes ./standin_*.gba)
tests/check_rom_standins.py builds them and checks the results automatically.
Real hacks can differ from these layouts - see DEVELOPER_NOTES.md (Lazarus)."""
import importlib.util, os, random
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('php', os.path.join(here, '..', 'pokemon_hack_porter.py'))
php = importlib.util.module_from_spec(spec); spec.loader.exec_module(php)
D = php.D
random.seed(1)

def official(nat):
    if not nat or nat > 1025: return ([0]*6, 0, 0)
    """(base stats, gender, growth) for a national dex number."""
    if nat <= 809:
        u = php.UU[nat]
        e = php.game_entry(9, nat, 0) or php.game_entry(8, nat, 0)
        stats = e[7:13] if e else [50] * 6
        return stats, u[0], u[1]
    e = php.game_entry(9, nat, 0) or php.game_entry(8, nat, 0)
    return e[7:13], e[1], e[2]

def table(entries, stride, goff, roff, count):
    """entries: {index: (stats, gender, growth)}"""
    t = bytearray(stride * count)
    for i in range(count):
        st, g, r = entries.get(i, ([0] * 6, 0, 0))
        o = i * stride
        t[o:o + 6] = bytes(st)
        for k in range(6, stride):                # filler that must not be mistaken for data
            t[o + k] = random.randrange(256)
        t[o + goff], t[o + roff] = g, r
    return bytes(t)

def junk(n):
    return bytes(random.randrange(256) for _ in range(n))

# 1) pokeemerald-expansion layout (Lazarus/Imperium): 0xC4-byte records, gender 0x12, growth 0x15
ent = {}
for sid in range(1, 906):
    ent[sid] = official(sid)
st, g, r = ent[653]; ent[653] = (st, 127, r)          # Lazarus: Fennekin 50/50
for sid, (nat, kind, suf) in D["FORMS"].items():
    ent[int(sid)] = official(nat)
open('standin_expansion.gba', 'wb').write(junk(5000) + table(ent, 0xC4, 0x12, 0x15, 1600) + junk(3000))

# 2) Gen 3 layout with DPE numbering (Gaia/Unbound): 28-byte records, gender 0x10, growth 0x13
ent = {}
for sid, (nat, form, kind, label) in D["DPE"].items():
    ent[int(sid)] = official(nat)
open('standin_dpe.gba', 'wb').write(junk(4000) + table(ent, 28, 0x10, 0x13, 1300) + junk(2000))


# 3) Lazarus v2.0 layout (found by Grok from the real ROM, Nov 2026): 32 MB ROM,
#    424-byte records starting with the Gen 3-encoded name, gender ratio at +186,
#    growth rate at +189. Like the real ROM, the other searches must not find it:
#    Bulbasaur's stats are changed, Bulbasaur's line has no names, and Sandslash's
#    gender breaks the Nidoran run.
STRIDE = 424
t = bytearray(random.randrange(256) for _ in range(STRIDE * 1000))
for nat in range(1, 906):
    o = official(nat)
    if not o[0]:
        continue
    st, g, r = o
    if nat in (1, 2, 3):
        st = [x + 5 for x in st]
    if nat == 28:
        g = 63
    if nat == 653:
        g = 127                                  # Lazarus: Fennekin 50/50
    b = nat * STRIDE
    name = b"" if nat in (1, 2, 3) else php.g3_encode(php.SPECIES[nat], len(php.SPECIES[nat]))[:12] + b"\xFF"
    t[b:b + len(name)] = name
    t[b + 13:b + 19] = bytes(st)
    t[b + 186], t[b + 189] = g, r
rom = junk(1_000_000) + bytes(t)
open('standin_lazarus.gba', 'wb').write(rom + bytes(33554432 - len(rom)))
