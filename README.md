# Pokémon Hack Porter

**Get your Pokémon out of ROM hacks and into PKHeX, PKVault, OpenHome and official games.**

Pokémon Hack Porter opens a save file from a supported ROM hack, shows you every Pokémon in your party and PC boxes, and exports the ones you pick as standard Pokémon files (`.pk3`, `.pk6`, `.pk7`). Those files can be imported into storage tools like OpenHome and PKVault, and from there moved into official games.

Your save file is only ever read — it is never changed.

---

## Supported ROM hacks

| ROM hack | Party | PC boxes | Notes |
|---|---|---|---|
| Pokémon Lazarus (v2.0) | ✅ | ✅ | |
| Pokémon Emerald Imperium (v1.3) | ✅ | ✅ | |
| Pokémon Unbound (v2.1) | ✅ | ✅ | |
| Pokémon Odyssey (v4.1) | ✅ | ✅ | |
| Pokémon Gaia (v3.2) | ✅ | ✅ | Poké Balls are always exported as regular Poké Balls for now |
| Pokémon Light Platinum | ✅ | ✅ | Load the hack's ROM too for reliable results (see below) |

Odyssey and Gaia saves look identical from the outside, so the program asks which game the save is from when you open one.

More hacks are planned. Other versions of the hacks above may work, but haven't been tested.

---

## Download

Go to the **[Releases](../../releases)** page and download the file for your system:

| System | Download | How to run |
|---|---|---|
| Windows | `Pokemon-Hack-Porter-Windows.zip` | Unzip, double-click `Pokemon-Hack-Porter.exe` |
| Linux / Steam Deck | `Pokemon-Hack-Porter-Linux.tar.gz` | Extract, double-click `Pokemon-Hack-Porter` (choose *Execute* if asked) |
| macOS | `Pokemon-Hack-Porter-macOS.zip` | Unzip, open `Pokemon Hack Porter.app` |

These include everything needed — no Python required.

**Security warnings are expected.** The app isn't signed by a paid certificate, so:
- **Windows** may say *"Windows protected your PC"* → click **More info → Run anyway**.
- **macOS** may refuse to open it → right-click the app → **Open** → **Open**.

### Or run the script directly

If you have Python 3.8 or newer, you can download `pokemon_hack_porter.py` instead and run it with:

```
python pokemon_hack_porter.py
```

(On Linux and Steam Deck use `python3`. To make it double-clickable there, right-click it → Properties → Permissions → tick *"Allow executing file as program"*, or run `chmod +x pokemon_hack_porter.py`.)

---

## How to use it

1. Click **Open Save…** and pick your ROM hack's `.sav` file.
2. Your party and PC boxes are listed. Party Pokémon are ticked automatically — click the box at the start of a row to tick or untick it.
3. Click any row to see full details: moves, IVs, EVs, Original Trainer, Poké Ball, and notes.
4. Click **Export Selected…**, choose a folder, and the files are written there.

### What the columns mean

- **Can go to** — the oldest game generation the Pokémon can be moved into. *Gen 3+* means it can go to any official game from Ruby/Sapphire onwards; *Gen 7+* means Sun/Moon or newer, and so on.
- **File** — the file type it will be saved as. Each Pokémon gets the oldest format that can hold all of its data: a Gen 1–3 Pokémon with Gen 1–3 moves becomes a `.pk3`; anything needing Gen 4–6 data becomes a `.pk6`; Alolan forms and Gen 7 moves need a `.pk7`.

### Keep original Poké Balls

Some balls (Cherish, Dusk, Dream, Beast…) don't exist in older games. By default, a Pokémon whose ball is the *only* thing tying it to a newer generation gets a regular Poké Ball instead, so it can go to older games. Tick **"Keep original Poké Balls"** to keep its real ball — it may then only be able to go to newer games.

### Light Platinum: the "Load ROM…" button

Light Platinum reused the numbers of old Pokémon for its Gen 4 Pokémon (its Starly is stored where Bellsprout normally is). To tell them apart reliably, click **Load ROM…** after opening your save and pick your **Light Platinum `.gba` file**. The program reads the hack's own list of Pokémon and moves from it. The ROM is only read, on your computer.

Without the ROM, Pokémon that were never nicknamed are recognised by their name; nicknamed ones can't be identified and are greyed out.

### Text mode (optional)

For scripting or systems without a window toolkit:

```
python pokemon_hack_porter.py "My Save.sav" --text            # party only
python pokemon_hack_porter.py "My Save.sav" --text --boxes    # party + PC boxes
```

Extra options: `-o FOLDER` (output folder), `--keep-balls`, `--rom "hack.gba"`, `--hack gaia` / `--hack odyssey`.

---

## Getting the files into OpenHome

OpenHome imports Pokémon files by **drag and drop**: select the exported files in your file manager and drag them onto an empty slot in an OpenHome box. You can drag many files at once — they fill the slots from there onwards. (OpenHome's *Open* button is only for save files.)

PKVault and PKHeX can import the same files.

## Moving them into official games

From OpenHome or PKHeX, the Pokémon can be placed into official game saves. On a modded 3DS, for example, you can back up a Sun/Moon save with **Checkpoint**, open it in OpenHome, drag the Pokémon into its boxes, and restore the edited save with Checkpoint. **Always back up your save first.**

---

## What carries over

**Kept:** species, nickname, Original Trainer name / gender / ID, personality value (so nature, gender and shininess stay the same), IVs, EVs, level and EXP, moves and PP Ups, friendship, Pokérus, markings, language, met level, Poké Ball, ability slot, contest stats, and Gen 3 ribbons (in `.pk3` files).

**Changed or dropped:**
- **Held items** are dropped.
- **Met location** becomes "traded", since ROM hack locations don't exist in official games.
- **Abilities:** the save only records which ability *slot* a Pokémon uses. Many hacks change what those slots contain, so exported Pokémon get the **official** ability for the same slot — it may differ from what the hack showed.
- **Hack-only Pokémon and forms** (fakemon, custom forms such as Lazarus's Mythic forms) can't exist in official games and aren't exported. Other alternate forms are exported as the regular form, except Alolan forms, which are kept.
- **Gen 8+ Pokémon and moves** (Sword/Shield, Legends, Scarlet/Violet) are listed but can't be exported yet.
- **Mints** and **Hyper Training** (before Gen 7) can't be stored in these formats.
- **Eggs** are skipped.

If anything about a Pokémon changes, the details panel says so.

## ⚠️ About legality

Pokémon from ROM hacks will **never pass legality checks** — they were caught in places and ways that don't exist in official games. That's fine for single-player use, emulators and storage tools, but:

- **Do not** use them online (trades, battles).
- **Do not** put them into the official **Pokémon Home** or **Pokémon Bank** — flagged Pokémon can get your account in trouble.

---

## Troubleshooting

**"Couldn't find an intact save in this file."**
Save from the game's own menu (Start → Save). Emulator *save states* don't update the `.sav` file. Also check you picked the `.sav` (or RetroArch `.srm`), usually 128 KB.

**"This save isn't from a supported ROM hack."**
The hack (or that version of it) isn't supported yet — see the list above.

**A Pokémon shows the wrong species or ability.**
Please open an issue with the details (see below).

**Sharing a save file online for a bug report?** Put it in a **.zip** first — some upload paths corrupt raw save files.

---

## Reporting problems / requesting a hack

Open an **[Issue](../../issues)** and include:
1. the ROM hack's name and version,
2. your save file, zipped,
3. what's in your party/boxes and what looks wrong.

Please **never** attach ROM files.

---

## Credits

- **[PKHeX](https://github.com/kwsch/PKHeX)** by Kaphotics and contributors — Pokémon file formats, species/move/ability data (GPL-3.0).
- **[OpenHome](https://github.com/andrewbenington/OpenHome)** by Andrew Benington and contributors — Unbound/CFRU species numbering, move list and PC format (GPL-3.0).
- **[pokeemerald-expansion](https://github.com/rh-hideout/pokeemerald-expansion)** by Rom Hacking Hideout (RHH) — save and Pokémon data layout used by Lazarus and Imperium.
- The creators of the supported ROM hacks.

## License

Pokémon Hack Porter is free software, released under the **GNU General Public License v3.0** — see [LICENSE](LICENSE).

Pokémon is © Nintendo, Game Freak and The Pokémon Company. This project is not affiliated with or endorsed by them, and does not include or distribute any ROMs.
