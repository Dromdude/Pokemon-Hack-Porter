# Developer notes

Everything needed to keep working on Pokémon Hack Porter: how it's built, how each hack is read, what has been verified, and what's still open. Written at the end of v1.1.1 development (Nov 2026).

**Never commit ROMs (`.gba`) to this repository.** Saves and test data only.

---

## Files

| Path | What it is |
|---|---|
| `pokemon_hack_porter.py` | The whole program (Python 3.8+, standard library + tkinter). Generated — don't edit by hand. |
| `tools/pokemon_hack_porter_src.py` | The source you edit. Same as the program, minus the embedded data (`DATA_BLOB = "@@DATA@@"`). |
| `tools/gen_data.py` | Builds `tools/data.json` (species/move/ability names, official personal data, ID mapping tables) from PKHeX, pokeemerald-expansion and OpenHome checkouts. Paths via env vars (see the file). |
| `tools/data.json` | The current data (so you don't need the checkouts unless the data changes). |
| `tools/build.py` | Embeds `data.json` into the source and writes `pokemon_hack_porter.py`. |
| `tools/make_synthetic_save.py` | Writes Gen 8/9 edge cases into a Lazarus save (`tests/saves/synthetic_gen89.sav`). |
| `tools/make_standin_roms.py` | Stand-in ROMs (random bytes + a species table in a given layout) for testing Load ROM without real ROMs. |
| `tests/saves/` | Real saves from the owner's playthroughs (one per hack) + synthetic saves. |
| `tests/expected.py` | **Ground truth**: every Pokémon in the saves as shown on in-game summary screens. |
| `tests/check_saves.py` | Checks the program against `expected.py`. |
| `.github/workflows/build.yml` | PyInstaller builds for Windows/macOS/Linux. Runs on release publish (attaches files) or by hand (Actions tab → artifacts, no release). |
| `.github/ISSUE_TEMPLATE/save-report.yml` | Form for users to send saves. |

Workflow: edit `tools/pokemon_hack_porter_src.py` → `python3 tools/build.py` → `python3 tests/check_saves.py` → regression check (below).

## How the program works

1. `read_gba_save()` — finds the newest intact save in a 128 KB GBA save. Sectors are 0x1000 bytes with a footer at 0xFF4 (section id u16, checksum u16, signature u32, save index u32). Sectors are grouped by save index; the checksum covers a size that varies by hack (3968, 0xFF4, 2000, others — found by brute force in `checksum_size()`).
2. `PROFILES` — one class per hack. `detect(save)` picks the hack; `read(save)` returns the party and boxes as decoded dicts; `species()`, `move()`, `ball()` map the hack's IDs to official ones. Odyssey and Gaia saves look alike, so the user picks.
3. `Entry._plan()` — works out the species/form, moves, ability slot, ball, level/EXP, gender, and the file format. Every reason a newer generation is needed goes into `need` (shown as "Can go to Gen N+").
4. Writers: `_pk3` (80 bytes), `_pk67` (232 bytes), `_pk89` (344 bytes party format — OpenHome's reader requires the party size). All decrypted, PKHeX layout. Met location = Link Trade, met date = export date, origin game Emerald / Alpha Sapphire / Ultra Sun / Sword / Scarlet.

### Format rule
Oldest format that holds all the data: ≤ Gen 3 → `.pk3`; ≤ 6 → `.pk6`; 7 → `.pk7`; Gen 8 → `.pk8` if the species/form exists in Sword/Shield, else `.pk9`; Gen 9 → `.pk9`. Moves a game can't use (PKHeX dummied-move tables) are dropped; the game that keeps more moves wins. Poké Balls only count if "Keep original Poké Balls" is ticked; otherwise a ball newer than the format becomes a Poké Ball.

### Per-hack save formats
| Hack | Profile | Pokémon format | Notes |
|---|---|---|---|
| Lazarus v2.0 | `ExpansionProfile` | pokeemerald-expansion 1.10+ bitfields (species 11 bits, 12-letter nicknames split across bytes, ball 6 bits, ability slot in ribbon word bits 29–30, hidden nature/mint at 0x12>>3, shiny flag 0x1E bit 14) | Species 1–905 = National Dex; higher IDs = forms/Gen 9 (`FORMS`, `FORMNUM`). Moves > 621 mapped by name (`MOVEMAP`). Balls from 1.10 (Strange = 0). |
| Emerald Imperium v1.3 | `ImperiumProfile` | Same as Lazarus | One 28-sector save (no backup), 0xFF4 data bytes per sector, boxes in sectors 17–25. |
| Unbound v2.1 | `UnboundProfile` | Party: plain Gen 3, unencrypted, unshuffled, no checksum. Boxes: CFRU 58-byte compact format (`decode_cfru58`) | Own save signatures (0x01121999 etc.). DPE species numbering (Gen 4+ = national + 53, from OpenHome's UnboundSpeciesMap). Ability bit = Hidden Ability, else PID&1. |
| Gaia v3.2 | `GaiaProfile` | Plain Gen 3, unencrypted (party and boxes) | DPE numbering. Ball numbering unconfirmed — every ball is exported as a Poké Ball. Ability bit confirmed = Hidden Ability. |
| Odyssey v4.1 | `OdysseyProfile` | Plain Gen 3, unencrypted, no checksum | FireRed layout. Moves up to 621. |
| Light Platinum | `LightPlatinumProfile` | Standard encrypted Gen 3 (Ruby layout) | Reuses old species numbers for Gen 4 Pokémon (Starly = 69, Bidoof = 35). Identified from the ROM's name table (11-byte records), or from the unchanged nickname without the ROM. |

## Load ROM (gender odds and level-up rates)

Hacks can change a species' gender ratio and growth rate; the save doesn't say which, and in Gen 3 gender is computed from the PID with the species' ratio. `RomTables` → `find_base_stats()` looks for the hack's species table and returns `{hack species ID: (gender ratio, growth rate)}`. `_plan()` then keeps the hack's level (adjusting EXP to the official curve) and gender (stored directly in `.pk6`+; in `.pk3` the PID is re-rolled by `reroll_pid()` keeping nature and shininess).

Search methods, in order (`STATS_DIAG` collects what each saw; shown in the error):
1. `_find_by_nidoran` — gender bytes of #28–#35 one record apart: 127, 254×3, 0×3, 191. Growth offset learned from official data.
2. `_find_by_bulbasaur` — Bulbasaur/Ivysaur/Venusaur base stats one record apart (record size 24–1024).
3. `_find_by_names` — expansion keeps names inside records: "Bulbasaur", "Ivysaur", "Venusaur" one record apart. Gender/growth bytes and their encoding learned by behaviour (`_learn_field`).

Tested on stand-in ROMs (Gen 3 28-byte records; expansion records of 196, 304, 336, 348 and 424 bytes; percentage-encoded genders; permuted growth numbering) and works for those.

### ⚠️ Open bug: Lazarus's real ROM isn't recognised
Errors from the owner's real Lazarus ROM (33,554,432 bytes):
- v1.1: `size 33554432, Bulbasaur x0` → Bulbasaur's official base stats (45 49 49 45 65 65) appear **nowhere**.
- Test build 2: `female x1526` (pattern FE ?? ?? 03) — no Nidoran run found.
- Test build 3: `FE x132100, nido x0, FE3 24:1533 32:1409 512:1262; Bulbasaur x0` → no run of 127, 254, 254, 254, 0, 0, 0, 191 at any spacing; the only "three 0xFE in a row" spacings are 24/32/512 (graphics).
- Test build 4 (name search): also failed; the Details line wasn't captured.

So Lazarus's species data is laid out or encoded differently from current pokeemerald-expansion (`struct SpeciesInfo` in `include/pokemon.h`, which has u8 genderRatio, eggCycles, friendship, growthRate in a row). Possibilities: an older or heavily modified expansion, gender/growth not stored as plain bytes, data split across several tables, or rebalanced Gen 1 data. **With the ROM in hand:** find `gSpeciesInfo`/`gBaseStats` (e.g. search for a known field pattern, or follow pointers from code that reads gender), note the record size and the offsets of gender ratio and growth rate, then add a method (or a Lazarus-specific profile option) for it. The expected in-game result is in `tests/expected.py` — Fennekin must come out female and every other Lazarus Pokémon unchanged.

Other hacks' real ROMs haven't been tried with Load ROM either.

## Testing

1. **Screenshots:** `python3 tests/check_saves.py` (add `lazarus.sav=path/to/Lazarus.gba` etc. to test ROMs). Must report 0 failures.
2. **Regression:** without a ROM, exports must be byte-identical to the previous version except for intended changes. Export every save in `tests/saves` with the old and new program (`--text --boxes -o DIR`, `--hack gaia` for Gaia) and `cmp` the files. (Met date = today, so compare on the same day.)
3. **File validity:** read exports back with OpenHome's library (`npm i pokemon-files`; `new PK8(buffer)` etc.) and compare fields; `toBytes()` round-trips identically except `.pk9` party stats, which that library doesn't keep.
4. **GUI:** tkinter; under Linux use Xvfb + xdotool for screenshots. Dark mode setting is saved in `~/.pokemon_hack_porter.json`.

## Verified against the games (Nov 2026)
All six hacks: species, level, gender, nature, moves, PP, met level, OT/ID and ball match the in-game summary screens (`tests/expected.py`); IVs confirmed via stat calculations and, for Gaia and Lazarus, the in-game IV letter grades. Expected differences: hack-only abilities get the official ability for the same slot (with a note); hack-only moves (e.g. Unbound's Metal Bash) are dropped; hack-only types/forms become the regular Pokémon.

## Releases
Version string: `VERSION` in the source. Publish a GitHub release with the tag (e.g. `1.2`) → the workflow builds and attaches `Pokemon-Hack-Porter-{Windows.zip,macOS.zip,Linux.tar.gz}`. Test builds: Actions → Build downloads → Run workflow (pick a branch) → artifacts.

## Ideas not done yet
- Fix Lazarus Load ROM (above).
- Gaia ball numbering (needs a save with non-Poké Balls).
- More hacks: Radical Red, Emerald Rogue, Inclement Emerald, Seaglass, Modern Emerald… (send saves via the issue form).
- ROM-read hack abilities (currently the official ability for the slot).
- Automatic releases when a merged PR bumps `VERSION`.
- Remember the ROM path per hack.
