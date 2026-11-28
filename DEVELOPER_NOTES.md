# Developer notes

Everything needed to keep working on Pokémon Hack Porter: how it's built, how each hack is read, what has been verified, and what's still open. Last updated for v1.2 (Nov 2026).

## How this project is worked on

Two AI assistants work on this repository, coordinated by the owner (Nick):
- **Claude** does the development: code, tests, builds, documentation, releases. Claude doesn't open ROM files.
- **Grok** answers questions that need data straight from a ROM (offsets, record sizes, byte values). Its answers get checked against official data and the owner's saves before anything is built in (lesson from the Lazarus reader, see below).

Rules that keep it smooth:
1. One assistant per task, each on its own branch; always start from the latest `main`.
2. Every change goes through a pull request; Nick merges.
3. Update this file whenever you change how something works, so the other assistant doesn't have to rediscover it.
4. Before merging: `python3 tests/check_saves.py` and `python3 tests/check_rom_standins.py` must both report 0 failures.

### ROM data requests
When development needs facts from a ROM, write a short request for Nick to paste to Grok: what to find, which species to report, and the official values to compare against. Ask for numbers, not files. Template:

```
This is a <hack name and version> ROM (GBA, built on <engine if known>).
I need facts about its <table, e.g. species data table (gSpeciesInfo / gBaseStats)>.
Please answer briefly:
1. The file offset where the table starts, and the size of one record in bytes.
2. Within a record, the offsets of: <fields, e.g. genderRatio, growthRate>.
3. The raw values of those fields for species <list of IDs and names>.
4. If a field isn't a plain single byte, explain how it's stored.
Official values for comparison: <e.g. Bulbasaur gender 31, growth 3; Nidoran F gender 254>.
```

Record the answer in this file (see "Known ROM layouts") and add a stand-in ROM with that layout to `tools/make_standin_roms.py` so the support stays tested without the real ROM.

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
| `tools/rom_data_export.py` | Developer-only tool (not in the releases): reads a hack's ROM with the porter's ROM reader and writes `<rom>_romdata.csv` with each Pokémon's gender ratio and growth rate (numbers only). Double-click and pick ROMs, or pass paths. Used to build per-hack data into the porter so the ROM isn't needed. |
| `tests/check_rom_standins.py` | Builds the stand-in ROMs and checks Load ROM gives the in-game results. |
| `tests/saves/` | Real saves from the owner's playthroughs (one per hack) + synthetic saves. |
| `tests/expected.py` | **Ground truth**: every Pokémon in the saves as shown on in-game summary screens. |
| `tests/check_saves.py` | Checks the program against `expected.py`. |
| `.github/workflows/build.yml` | PyInstaller builds for Windows/macOS/Linux. Runs on release publish (attaches files) or by hand (Actions tab → artifacts, no release). |
| `.github/ISSUE_TEMPLATE/save-report.yml` | Form for users to send saves. |

Workflow: edit `tools/pokemon_hack_porter_src.py` → `python3 tools/build.py` → `python3 tests/check_saves.py` and `python3 tests/check_rom_standins.py` → regression check (below). Always rebuild with `tools/build.py` before committing: the release workflow packages `pokemon_hack_porter.py`, not the source.

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

Hacks can change a species' gender ratio and growth rate; the save doesn't say which, and in Gen 3 gender is computed from the PID with the species' ratio.

**Manual switches (v1.2, the main fix):** in the window, clicking a row's ♂/♀ flips its gender and clicking Lv asks for the level the game shows (`Entry(..., gender=, level=)`; text mode `--set-gender "Party 4=F"`, `--set-level "BOX1, slot 2=5"`). Changed values show `*` and a note. This works for every hack without any ROM data; Load ROM is a bonus where it works.

**Known gender changes and "?" (v1.2):** `Profile.known_genders` holds gender ratios confirmed from real saves (Lazarus: Fennekin line 653–655 = 127, since a female Fennekin with personality byte 58 is impossible at the official 31). `Profile.check_genders = True` (Lazarus) marks every other mixed-ratio gender with `?` when no ROM data is loaded, telling the user to compare with the game. Add a species to `known_genders` whenever a mismatch is confirmed in-game.

**Safety check (v1.2):** `stats_agreement()` compares the ROM data with official gender ratio + growth rate for Pokémon #1–251. A real hack changes a few; if fewer than 75% match (or fewer than 50 can be compared), `RomTables` rejects the data (`self.rejected`) and says so, instead of producing wrong genders/levels. `RomTables` → `find_base_stats()` looks for the hack's species table and returns `{hack species ID: (gender ratio, growth rate)}`. `_plan()` then keeps the hack's level (adjusting EXP to the official curve) and gender (stored directly in `.pk6`+; in `.pk3` the PID is re-rolled by `reroll_pid()` keeping nature and shininess).

Search methods, in order (`STATS_DIAG` collects what each saw; shown in the error and by `tests/check_saves.py`):
1. `_find_by_nidoran` — gender bytes of #28–#35 one record apart: 127, 254×3, 0×3, 191. Growth offset learned from official data.
2. `_find_by_bulbasaur` — Bulbasaur/Ivysaur/Venusaur base stats one record apart (record size 24–1024).
3. `_find_by_names` — expansion keeps names inside records: "Bulbasaur", "Ivysaur", "Venusaur" one record apart. Gender/growth bytes and their encoding learned by behaviour (`_learn_field`).
4. `_find_lazarus` (added by Grok, v1.1.3) — turned out to misread the real ROM (see Lazarus status); kept, but its output fails the safety check. Only runs for 32 MB ROMs when the others find nothing; anchors on the names Fennekin, Pikachu, Caterpie, Eevee and Vulpix and walks records in both directions.

Tested on stand-in ROMs (Gen 3 28-byte records; expansion records of 196, 304, 336, 348 and 424 bytes; percentage-encoded genders; permuted growth numbering) and works for those.

### Known ROM layouts
| Hack | ROM size | Record size | Name | Gender ratio | Growth rate | Found by |
|---|---|---|---|---|---|---|
| Lazarus v2.0 | 33,554,432 | unknown | — | — | — | not found yet (Grok's 424-byte reading proved wrong, see below) |
| pokeemerald-expansion (current) | varies | 196+ bytes (more with options) | inside the record | +0x12 in the default build | +0x15 | expansion source |
| Gen 3 / CFRU / DPE (Gaia, Unbound, Odyssey, Light Platinum) | 16–32 MB | 28 bytes | separate table | +0x10 | +0x13 | standard layout |

**Lazarus status: unsolved.** Its ROM doesn't contain Bulbasaur's official base stats, and none of the general searches (1–3) found the table (Details lines from the real ROM: `Bulbasaur x0`, then `FE x132100, nido x0, FE3 24:1533 32:1409 512:1262`). Grok's `_find_lazarus` (v1.1.3) anchors on names in 424-byte records, but checking its output (`tools/rom_data_export.py` on the real ROM, kept in `tests/data/lazarus_v2.0_misread_romdata.csv`) showed it misreads most species: only 71 of 135 Gen 1–2 Pokémon match official data, Magneton/Electrode read as always male, Murkrow reads male (in-game female), 65 entries hold the next species' values. The safety check rejects it, so it's effectively off.

Follow-up attempts by Grok (no ARM disassembler available to it) didn't find the real table: the named 212-byte records aren't one table (offsets not multiples of 212 apart, Bulbasaur missing), and candidates found by matching a few values (#29 = 254, #32 = 0, #81 = 255 at strides 64–336) were random hits (Candidate A matched official data for 2 of 40 species; ~2,000 such hits are expected by chance in 32 MB). **To finish it:** disassemble the gender routine (`GetGenderFromSpeciesAndPersonality`, e.g. with Ghidra) and follow its table pointer. Any answer must pass these checks from the owner's save: #198 Murkrow female with personality byte 76 (ratio > 76, growth 3); #179 Mareep female, byte 4 (> 4, growth 3); #653 Fennekin female, byte 58 (> 58, growth 3); #37 Vulpix female, byte 73 (> 73); #285 Shroomish male, byte 177 (≤ 177, growth 2); #133 Eevee male, byte 166 (≤ 166). Until then, users fix Fennekin/Braixen's gender with the ♂/♀ switch.

Real ROMs tried with Load ROM so far: Lazarus (not readable; rejected by the safety check). The others are untested with their real ROMs; if one fails, the Details line in the error says what the searches saw, and a ROM data request to Grok can fill in the layout.

## Testing

1. **Screenshots:** `python3 tests/check_saves.py` (add `lazarus.sav=path/to/Lazarus.gba` etc. to test real ROMs, `--only lazarus.sav` for one save). Must report 0 failures.
2. **Stand-in ROMs:** `python3 tests/check_rom_standins.py`. Must report 0 failures.
3. **Regression:** without a ROM, exports must be byte-identical to the previous version except for intended changes. Export every save in `tests/saves` with the old and new program (`--text --boxes -o DIR`, `--hack gaia` for Gaia) and `cmp` the files. (Met date = today, so compare on the same day.)
4. **File validity:** read exports back with OpenHome's library (`npm i pokemon-files`; `new PK8(buffer)` etc.) and compare fields; `toBytes()` round-trips identically except `.pk9` party stats, which that library doesn't keep.
5. **GUI:** tkinter; under Linux use Xvfb + xdotool for screenshots. Dark mode setting is saved in `~/.pokemon_hack_porter.json`.

## Verified against the games (Nov 2026)
All six hacks: species, level, gender, nature, moves, PP, met level, OT/ID and ball match the in-game summary screens (`tests/expected.py`); IVs confirmed via stat calculations and, for Gaia and Lazarus, the in-game IV letter grades. Expected differences: hack-only abilities get the official ability for the same slot (with a note); hack-only moves (e.g. Unbound's Metal Bash) are dropped; hack-only types/forms become the regular Pokémon.

## Releases
Version string: `VERSION` in the source. Publish a GitHub release with the tag (e.g. `1.2`) → the workflow builds and attaches `Pokemon-Hack-Porter-{Windows.zip,macOS.zip,Linux.tar.gz}`. Test builds: Actions → Build downloads → Run workflow (pick a branch) → artifacts.

### Built-in hack data (planned)
Only once a hack's ROM reads correctly (it must pass the safety check and the checks from saves). Goal: genders and levels right without loading the ROM. Nick runs `tools/rom_data_export.py` on each hack ROM and sends the CSVs; only the entries that differ from official data get built into the porter, per hack version (identify the version by the save profile; the CSV header has the ROM size and CRC32). A loaded ROM still takes priority over built-in data.

## Ideas not done yet
- **Hack-only forms (planned, on hold):** flag Pokémon whose form only exists in the hack, with a note like "Ice/Dark form only exists in Odyssey, so it will be a regular Poochyena", and leave them unticked by default. Two cases: forms with their own species number (e.g. likely Lazarus's mythic forms) can be detected from the save; species the hack changed in place (e.g. Odyssey's Ice/Dark Poochyena line, same number as official Poochyena) need a per-hack list from the hack's documentation or ROM data. Optionally save a short report with each export listing lost forms, abilities and moves.
- Find Lazarus's real species table (checks above).
- Try Load ROM with the other hacks' real ROMs (`tools/rom_data_export.py` + compare with official data).
- Gaia ball numbering (needs a save with non-Poké Balls).
- More hacks: Radical Red, Emerald Rogue, Inclement Emerald, Seaglass, Modern Emerald… (send saves via the issue form).
- ROM-read hack abilities (currently the official ability for the slot).
- Automatic releases when a merged PR bumps `VERSION`.
- Remember the ROM path per hack.
