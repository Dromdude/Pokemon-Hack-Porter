#!/usr/bin/env python3
"""
Pokemon Hack Porter
===================
Opens a ROM hack save file and exports its Pokemon (party and PC boxes) as
standard Pokemon files (.pk3 / .pk6 / .pk7 / .pk8 / .pk9) that PKHeX, PKVault
and OpenHome can import.

Supported ROM hacks:
    Pokemon Lazarus (v2.0)
    Pokemon Emerald Imperium (v1.3)
    Pokemon Odyssey (v4.1)
    Pokemon Light Platinum
    Pokemon Unbound (v2.1)
    Pokemon Gaia (v3.2)

How to use:
    Double-click this file (or run:  python3 pokemon_hack_porter.py)
    -> click "Open Save...", then "Load ROM..." and pick the hack's .gba file,
       tick the Pokemon you want, click "Export Selected...".
    Loading the ROM lets the program match genders and levels exactly as the hack
    shows them (hacks can change gender odds and level-up speed). It's only read.

    No window toolkit available (some Linux setups)? It falls back to text mode:
        python3 pokemon_hack_porter.py "My Save.sav" --text            party only
        python3 pokemon_hack_porter.py "My Save.sav" --text --boxes    party + all boxes
        add  --rom "My Hack.gba"  to use the hack's ROM

Each Pokemon gets the OLDEST file format that can hold all of its data:
    .pk3  Gen 1-3 Pokemon with Gen 1-3 moves and abilities
    .pk6  anything up to Gen 6 (also used for Gen 4-5 data)
    .pk7  anything up to Gen 7 (Alolan forms, Gen 7 moves)
    .pk8  Gen 8 data, for Pokemon that exist in Sword/Shield
    .pk9  Gen 9 data, or Gen 8 Pokemon that only exist in Scarlet/Violet

Carried over: species, nickname, OT name/gender/IDs, personality value (nature,
gender, shininess), IVs, EVs, level/EXP, moves and PP Ups, friendship, Pokerus,
markings, language, met level, Poke Ball, ability, contest stats (and Gen 3
ribbons in .pk3 files). Dropped: held items. Met location becomes "traded",
since ROM hack locations don't exist in official games. Eggs are skipped.

Your save file is only read, never modified. Needs Python 3.8+ and nothing else.

Copyright (C) 2026 the Pokemon Hack Porter authors.
This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version. It is distributed WITHOUT ANY WARRANTY; see the LICENSE file.

Reference data comes from PKHeX (GPL-3.0), OpenHome (GPL-3.0) and
pokeemerald-expansion by Rom Hacking Hideout. Not affiliated with Nintendo,
Game Freak or The Pokemon Company.
"""
import argparse
import base64
import datetime
import json
import os
import re
import struct
import subprocess
import sys
import zlib

APP_NAME = "Pokémon Hack Porter"
VERSION = "1.2"

# Reference data: species/move/ability names, official base data and the
# ROM-hack-to-official ID tables. Built from PKHeX and pokeemerald-expansion
# sources (zlib + base64).
DATA_BLOB = "@@DATA@@"
D = json.loads(zlib.decompress(base64.b64decode("".join(DATA_BLOB.split()))).decode("utf-8"))
SPECIES, MOVES, ABILITIES = D["SPECIES"], D["MOVES"], D["ABILITIES"]
EXP_FORMS, EXP_MOVES = D["FORMS"], D["MOVEMAP"]
AO, UU, ALOLA = D["AO"], D["UU"], D["ALOLA"]
G3INT, G3AB, G3GROW = D["G3INT"], D["G3AB"], D["G3GROW"]
DPE, CFRUMOVES, BASE_PP = D["DPE"], D["CFRUMOVES"], D["PP"]
FORMNUM, G9INT = D["FORMNUM"], D["G9INT"]
# Gen 8/9 games: name, personal data, moves that can't be used there, last move
GAMES = {8: ("Sword/Shield", D["SWSH"], set(D["DUMMY8"]), 826),
         9: ("Scarlet/Violet", D["SV"], set(D["DUMMY9"]), 919)}
BALL_LIMIT = {3: 12, 6: 25, 7: 26, 8: 26, 9: 26}

NATURES = ["Hardy", "Lonely", "Brave", "Adamant", "Naughty", "Bold", "Docile", "Relaxed",
           "Impish", "Lax", "Timid", "Hasty", "Serious", "Jolly", "Naive", "Modest", "Mild",
           "Quiet", "Bashful", "Rash", "Calm", "Gentle", "Sassy", "Careful", "Quirky"]
def gen_of_ball(b):
    return 3 if b <= 12 else 4 if b <= 24 else 5 if b == 25 else 7


OFFICIAL_BALLS = {1: "Master", 2: "Ultra", 3: "Great", 4: "Poké", 5: "Safari", 6: "Net",
                  7: "Dive", 8: "Nest", 9: "Repeat", 10: "Timer", 11: "Luxury", 12: "Premier",
                  13: "Dusk", 14: "Heal", 15: "Quick", 16: "Cherish", 17: "Fast", 18: "Level",
                  19: "Lure", 20: "Heavy", 21: "Love", 22: "Friend", 23: "Moon", 24: "Sport",
                  25: "Dream", 26: "Beast"}


class ExportError(Exception):
    """A problem worth showing to the user as a plain message."""


# =============================================================== text
G3_CHARS = {0x00: " ", 0x1B: "é", 0xAB: "!", 0xAC: "?", 0xAD: ".", 0xAE: "-", 0xB0: "…",
            0xB1: "“", 0xB2: "”", 0xB3: "‘", 0xB4: "’", 0xB5: "♂", 0xB6: "♀", 0xB8: ",",
            0xB9: "×", 0xBA: "/", 0xF0: ":"}
for _i in range(10):
    G3_CHARS[0xA1 + _i] = str(_i)
for _i in range(26):
    G3_CHARS[0xBB + _i] = chr(65 + _i)
    G3_CHARS[0xD5 + _i] = chr(97 + _i)
G3_REV = {v: k for k, v in G3_CHARS.items()}
G3_REV["'"] = 0xB4


def g3_decode(raw):
    out = ""
    for c in raw:
        if c == 0xFF:
            break
        out += G3_CHARS.get(c, "?")
    return out


def g3_encode(text, length):
    b = bytes(G3_REV.get(ch, 0xAC) for ch in text[:length])
    return b + b"\xFF" * (length - len(b))


def g6_encode(text):
    """Gen 6/7 strings: UTF-16LE, up to 12 characters + terminator (26 bytes)."""
    text = text.replace("♂", "").replace("♀", "")[:12]
    b = text.encode("utf-16-le")
    return b + b"\x00" * (26 - len(b))


# =============================================================== official game rules
def gen_of_species(nat):
    for g, last in enumerate((151, 251, 386, 493, 649, 721, 809, 905, 1025), 1):
        if nat <= last:
            return g
    return 99


def gen_of_move(m):
    for g, last in enumerate((165, 251, 354, 467, 559, 621, 742, 826, 919), 1):
        if m <= last:
            return g
    return 99


def exp_for_level(group, n):
    if n <= 1:
        return 0
    c = n ** 3
    if group == 0:   # Medium Fast
        return c
    if group == 1:   # Erratic
        if n <= 50: return c * (100 - n) // 50
        if n <= 68: return c * (150 - n) // 100
        if n <= 98: return c * ((1911 - 10 * n) // 3) // 500
        return c * (160 - n) // 100
    if group == 2:   # Fluctuating
        if n <= 15: return c * ((n + 1) // 3 + 24) // 50
        if n <= 36: return c * (n + 14) // 50
        return c * (n // 2 + 32) // 50
    if group == 3:   # Medium Slow
        return 6 * c // 5 - 15 * n * n + 100 * n - 140
    if group == 4:   # Fast
        return 4 * c // 5
    return 5 * c // 4  # Slow


def level_for_exp(group, exp):
    lvl = 1
    while lvl < 100 and exp_for_level(group, lvl + 1) <= exp:
        lvl += 1
    return lvl


def game_entry(fmt, nat, form):
    """Sword/Shield (8) or Scarlet/Violet (9) data:
    [present in game, gender ratio, growth, ability1, ability2, hidden, type1] or None."""
    return GAMES[fmt][1].get(str(nat) if not form else "%d:%d" % (nat, form))


def base_data(nat, form, fmt):
    """[gender ratio, growth, ability1, ability2, hidden] from official games."""
    if fmt in (8, 9):
        e = game_entry(fmt, nat, form)
        return e[1:6] if e else None
    if form == 1 and str(nat) in ALOLA:
        return ALOLA[str(nat)]
    if fmt == 6 and nat <= 721:
        return AO[nat]
    if nat <= 809 and form == 0:
        return UU[nat]
    for g in (9, 8):             # Gen 8/9 Pokemon: newest data available
        e = game_entry(g, nat, form)
        if e:
            return e[1:6]
    return None


# =============================================================== GBA save reading
SECTOR = 0x1000
SIGNATURES = (0x08012025,                          # official games and most hacks
              0x01121999, 0x01122000, 0x01121998)  # Pokemon Unbound


def sector_checksum(data, size):
    total = sum(struct.unpack_from("<%dI" % (size // 4), data, 0)) & 0xFFFFFFFF
    return ((total >> 16) + (total & 0xFFFF)) & 0xFFFF


def checksum_size(sector):
    """How many bytes the sector's checksum covers (games and hacks differ),
    or None if no size matches, i.e. the sector is damaged."""
    want = struct.unpack_from("<H", sector, 0xFF6)[0]
    for size in (3968, 0xFF4, 2000):
        if sector_checksum(sector, size) == want:
            return size
    total = 0
    for i, w in enumerate(struct.unpack_from("<1021I", sector, 0)):
        total = (total + w) & 0xFFFFFFFF
        if ((total >> 16) + (total & 0xFFFF)) & 0xFFFF == want:
            return (i + 1) * 4
    return None


class GbaSave:
    """The newest intact save inside a GBA save file.
    Handles the normal layout (two copies of 14 sectors, 3968 data bytes each)
    and variants such as one copy of 28 sectors with 4084 data bytes each."""

    def __init__(self, secs, data_size, signature=SIGNATURES[0]):
        self.secs, self.data_size, self.signature = secs, data_size, signature
        self.count = len(secs)

    def joined(self, first, last):
        """Concatenate the data of sectors first..last (inclusive)."""
        return b"".join(self.secs[k][:self.data_size] for k in range(first, last + 1))


def read_gba_save(path):
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError as e:
        raise ExportError("Couldn't open the save file:\n%s" % e)
    if len(raw) < 32 * SECTOR:
        raise ExportError("This doesn't look like a GBA Pokemon save (the file is too small).")
    groups, sigs = {}, {}   # save counter -> {sector id: sector}
    for i in range(32):
        s = raw[i * SECTOR:(i + 1) * SECTOR]
        sid, chk, sig, idx = struct.unpack_from("<HHII", s, 0xFF4)
        if sig in SIGNATURES and sid < 32:
            groups.setdefault(idx, {})[sid] = s
            sigs[idx] = sig
    for idx in sorted(groups, reverse=True):          # newest first
        secs = groups[idx]
        if sorted(secs) != list(range(len(secs))) or len(secs) < 14:
            continue
        sizes = [checksum_size(s) for s in secs.values()]
        if None not in sizes:
            return GbaSave(secs, 0xFF4 if max(sizes) > 3968 else 3968, sigs[idx])
    raise ExportError("Couldn't find an intact save in this file.\n"
                      "Make sure it's a .sav from a supported ROM hack, and that you've saved "
                      "from the in-game menu (save states don't update the .sav file).")


# =============================================================== ROM hack profiles
class Profile:
    """Describes one ROM hack: how its save stores Pokemon and how its IDs map
    to official ones. Add a new subclass to support another hack."""
    name = short = "?"
    custom_abilities = False   # True if the hack is known to change species' abilities
    needs_rom = False          # True if the hack's ROM helps identify Pokemon
    rom = None
    # Gender ratios this hack is known to change {hack species number: ratio}, confirmed
    # from real saves; and whether genders should be checked against the game when
    # the hack's own data isn't available (the hack changes gender odds we can't read).
    known_genders = {}
    check_genders = False

    def detect(self, save):
        """Return True if the save looks like it belongs to this hack."""
        raise NotImplementedError

    def read(self, save):
        """Return (trainer name, list of (location label, is_party, decoded mon))."""
        raise NotImplementedError


ORDERS = ["GAEM", "GAME", "GEAM", "GEMA", "GMAE", "GMEA", "AGEM", "AGME", "AEGM", "AEMG",
          "AMGE", "AMEG", "EGAM", "EGMA", "EAGM", "EAMG", "EMGA", "EMAG", "MGAE", "MGEA",
          "MAGE", "MAEG", "MEGA", "MEAG"]


class ExpansionProfile(Profile):
    """Hacks built on pokeemerald-expansion 1.10+ (Emerald-style save,
    12-letter nicknames, National Dex species numbers up to #905)."""
    sectors, data_size = 14, 3968      # save layout
    storage = (5, 13)                  # sectors holding the PC boxes
    # pokeemerald-expansion ball IDs -> official ball IDs
    #           Strange Poke Great Ultra Master Premier Heal Net Nest Dive Dusk Timer Quick
    BALLS = [4, 4, 3, 2, 1, 12, 14, 6, 8, 7, 13, 10, 15,
             # Repeat Luxury Level Lure Moon Friend Love Fast Heavy Dream Safari Sport Park Beast
             9, 11, 18, 19, 23, 22, 21, 17, 20, 25, 5, 24, 4, 26,
             16]  # Cherish

    def species(self, sid, m=None):
        """-> (national dex, kind, form name) or None if unknown."""
        if 1 <= sid <= 905:
            return sid, "base", ""
        f = EXP_FORMS.get(str(sid))
        return tuple(f) + (FORMNUM.get(str(sid)),) if f else None

    def move(self, mid):
        return mid if mid <= 621 else EXP_MOVES.get(str(mid))

    def ball(self, b):
        return self.BALLS[b] if b < len(self.BALLS) else 4

    def decode(self, b, party):
        pid, otid = struct.unpack_from("<II", b, 0)
        if (pid == 0 and otid == 0) or not b[0x13] & 0x02:   # empty slot / no species
            return None
        key = pid ^ otid
        dec = b"".join(struct.pack("<I", struct.unpack_from("<I", b, 32 + i)[0] ^ key)
                       for i in range(0, 48, 4))
        order = ORDERS[pid % 24]
        sub = {order[i]: dec[i * 12:(i + 1) * 12] for i in range(4)}
        G, A, E, M = sub["G"], sub["A"], sub["E"], sub["M"]
        m = {"pid": pid, "otid": otid,
             "checksum_ok": (sum(struct.unpack("<24H", dec)) & 0xFFFF)
             == struct.unpack_from("<H", b, 0x1C)[0]}
        m["lang"], m["hidden_nature"] = b[0x12] & 7, b[0x12] >> 3
        m["bad_egg"], egg_flag = bool(b[0x13] & 1), bool(b[0x13] & 4)
        m["ot_raw"], m["markings"] = bytes(b[0x14:0x1B]), b[0x1B] & 0xF
        m["shiny_flag"] = bool(struct.unpack_from("<H", b, 0x1E)[0] & 0x4000)
        s0, item, x = struct.unpack_from("<HHI", G, 0)
        m["species_id"], m["item"] = s0 & 0x7FF, item & 0x3FF
        m["exp"], nick11 = x & 0x1FFFFF, (x >> 21) & 0xFF
        m["pp_ups"], m["friendship"] = G[8], G[9]
        w = struct.unpack_from("<H", G, 10)[0]
        m["ball_raw"], nick12 = w & 0x3F, (w >> 6) & 0xFF
        m["nick_raw"] = bytes(b[8:18]) + bytes([nick11, nick12])
        mv = struct.unpack_from("<4H", A, 0)
        m["moves_raw"] = [v & 0x7FF for v in mv]
        m["pp"] = [v & 0x7F for v in A[8:12]]
        m["hyper"] = [bool(mv[3] & 0x4000), bool(mv[3] & 0x8000)] + [bool(v & 0x80) for v in A[8:12]]
        m["evs"], m["contest"] = list(E[0:6]), list(E[6:12])     # hp atk def spe spa spd
        m["pokerus"] = M[0]
        org = struct.unpack_from("<H", M, 2)[0]
        m["met_level"], m["ot_gender"], m["game"] = org & 0x7F, org >> 15, (org >> 7) & 0xF
        iv, rib = struct.unpack_from("<II", M, 4)
        m["ivs"] = [(iv >> (5 * i)) & 31 for i in range(6)]      # hp atk def spe spa spd
        m["egg"] = bool(iv & 0x40000000) or egg_flag
        m["ribbons"], m["ability_num"], m["fateful"] = rib & 0x07FFFFFF, (rib >> 29) & 3, rib >> 31
        m["level"] = b[84] if party else None
        return m

    def detect(self, save):
        if save.count != self.sectors or save.data_size != self.data_size or \
                save.signature != SIGNATURES[0]:
            return False
        secs = save.secs
        count = struct.unpack_from("<I", secs[1], 0x234)[0]
        if not 0 <= count <= 6:
            return False
        for i in range(count):
            m = self.decode(secs[1][0x238 + i * 100: 0x238 + (i + 1) * 100], True)
            if m and (not m["checksum_ok"] or not 0 < m["species_id"] <= D["MAXEXP"] + 200):
                return False
            if m and not m["egg"] and m["game"] != 3:      # made in an Emerald-based game
                return False
        return True

    def read(self, save):
        secs, out = save.secs, []
        count = struct.unpack_from("<I", secs[1], 0x234)[0]
        for i in range(count):
            m = self.decode(secs[1][0x238 + i * 100: 0x238 + (i + 1) * 100], True)
            if m:
                out.append(("Party %d" % (i + 1), True, m))
        pc = save.joined(*self.storage)
        names_at = 4 + 420 * 80
        for box in range(14):
            name = g3_decode(pc[names_at + box * 9: names_at + box * 9 + 9]) or "Box %d" % (box + 1)
            for slot in range(30):
                o = 4 + (box * 30 + slot) * 80
                m = self.decode(pc[o:o + 80], False)
                if m:
                    out.append(("%s, slot %d" % (name, slot + 1), False, m))
        return g3_decode(secs[0][0:8]), out


class LazarusProfile(ExpansionProfile):
    name, short = "Pokémon Lazarus (v2.0)", "Lazarus"
    # Fennekin is female in-game with personality byte 58, so Lazarus raised its ratio
    # (official 31); 50/50 assumed, and for its evolutions too.
    known_genders = {653: 127, 654: 127, 655: 127}
    check_genders = True


class ImperiumProfile(ExpansionProfile):
    """Emerald Imperium keeps a single 28-sector save (no backup copy) with
    4084 data bytes per sector; the PC boxes live in sectors 17-25."""
    name, short = "Pokémon Emerald Imperium (v1.3)", "Imperium"
    sectors, data_size = 28, 0xFF4
    storage = (17, 25)


def decode_gen3(b, party, encrypted=True):
    """Decode a Pokemon in the original Gen 3 format (as in Ruby/Sapphire/Emerald/
    FireRed). Some hacks store it unencrypted; those also skip the checksum."""
    pid, otid = struct.unpack_from("<II", b, 0)
    if (pid == 0 and otid == 0) or not b[0x13] & 0x02:
        return None
    if encrypted:
        key = pid ^ otid
        dec = b"".join(struct.pack("<I", struct.unpack_from("<I", b, 32 + i)[0] ^ key)
                       for i in range(0, 48, 4))
        order = ORDERS[pid % 24]
        sub = {order[i]: dec[i * 12:(i + 1) * 12] for i in range(4)}
        G, A, E, M = sub["G"], sub["A"], sub["E"], sub["M"]
    else:
        dec = bytes(b[32:80])
        G, A, E, M = dec[0:12], dec[12:24], dec[24:36], dec[36:48]
    m = {"pid": pid, "otid": otid, "lang": b[0x12] & 7, "hidden_nature": 0,
         "bad_egg": bool(b[0x13] & 1), "ot_raw": bytes(b[0x14:0x1B]),
         "markings": b[0x1B] & 0xF, "shiny_flag": False}
    m["species_id"], m["item"], m["exp"] = struct.unpack_from("<HHI", G, 0)
    m["pp_ups"], m["friendship"] = G[8], G[9]
    m["nick_raw"] = bytes(b[8:18])
    m["moves_raw"] = list(struct.unpack_from("<4H", A, 0))
    m["pp"] = list(A[8:12])
    m["hyper"] = [False] * 6
    m["evs"], m["contest"] = list(E[0:6]), list(E[6:12])
    m["pokerus"] = M[0]
    org = struct.unpack_from("<H", M, 2)[0]
    m["met_level"], m["game"] = org & 0x7F, (org >> 7) & 0xF
    m["ball_raw"], m["ot_gender"] = (org >> 11) & 0xF, org >> 15
    iv, rib = struct.unpack_from("<II", M, 4)
    m["ivs"] = [(iv >> (5 * i)) & 31 for i in range(6)]
    m["egg"] = bool(iv & 0x40000000) or bool(b[0x13] & 4)
    m["ability_num"] = iv >> 31
    m["ribbons"], m["fateful"] = rib & 0x07FFFFFF, rib >> 31
    if encrypted:
        m["checksum_ok"] = (sum(struct.unpack("<24H", dec)) & 0xFFFF) == \
            struct.unpack_from("<H", b, 0x1C)[0]
    else:   # no checksum stored, so sanity-check the values instead
        m["checksum_ok"] = 0 < m["species_id"] < 1500 and m["exp"] < 2000000 and \
            all(v <= 99 for v in m["pp"])
    m["level"] = b[84] if party else None
    return m


NAT_FROM_G3 = {v: k for k, v in enumerate(G3INT) if k}


def g3_species_to_national(sid):
    """Official Gen 3 internal species number -> National Dex number."""
    return NAT_FROM_G3.get(sid) if 1 <= sid <= 411 else None


def _norm(s):
    s = s.replace("♀", "F").replace("♂", "M").upper()
    return "".join(ch for ch in s if ch.isalnum())


SPECIES_BY_NAME = {_norm(n): i for i, n in enumerate(SPECIES) if i}
MOVES_BY_NAME = {_norm(n): i for i, n in enumerate(MOVES) if i}
# Gen 3 spellings that were changed or shortened in later games
MOVE_ALIASES = {"VICEGRIP": "VISEGRIP", "HIJUMPKICK": "HIGHJUMPKICK",
                "FAINTATTACK": "FEINTATTACK", "SMELLINGSALT": "SMELLINGSALTS"}


def name_to_id(name, table, aliases=None):
    n = _norm(name)
    if aliases:
        n = aliases.get(n, n)
    if n in table:
        return table[n]
    hits = [i for k, i in table.items() if k.startswith(n)] if len(n) >= 8 else []
    return hits[0] if len(hits) == 1 else None      # names shortened to fit Gen 3


def read_name_table(rom, first, second, rec_len, limit):
    """Find a table of fixed-length Gen 3 strings whose first two entries are
    known, and return all entries as text."""
    pad = rec_len - len(first)
    pos = rom.find(first)
    while pos != -1:
        nxt = rom[pos + rec_len: pos + rec_len + len(second)]
        if nxt == second:
            names = []
            for i in range(limit):
                rec = rom[pos + i * rec_len: pos + (i + 1) * rec_len]
                if len(rec) < rec_len or 0xFF not in rec:
                    break
                body = rec[:rec.index(0xFF)]
                if any(c not in G3_CHARS for c in body):
                    break
                names.append(g3_decode(rec))
            return names
        pos = rom.find(first, pos + 1)
    return None


BASE_STATS_START = (bytes([45, 49, 49, 45, 65, 65]),      # Bulbasaur  HP Atk Def Spe SpA SpD
                    bytes([60, 62, 63, 60, 80, 80]),      # Ivysaur
                    (bytes([80, 82, 83, 80, 100, 100]),   # Venusaur, or (if a hack changed it)
                     bytes([39, 52, 43, 65, 60, 50])))    # Charmander one record later
MAX_RECORD = 1024      # pokeemerald-expansion records grow with options like following Pokemon


STATS_DIAG = []        # what the search saw, shown if it fails (helps fix new hacks)
# Gender ratios of Sandslash, the Nidoran families and Clefairy (#28-#35), which hacks
# don't change: 50/50, three always-female, three always-male, 75% female.
NIDO_GENDERS = (127, 254, 254, 254, 0, 0, 0, 191)



def _find_lazarus(rom):
    """Lazarus v2.0 (32 MB) stores species data in 424-byte records.
    Gender ratio is at offset +186, growth rate at +189. Many records start
    with a Gen-3 encoded name. Anchor on known names and walk both directions
    to build a {species_id: (gender, growth)} table."""
    if len(rom) != 33554432:
        return []
    def g3_decode(raw):
        out = ""
        for c in raw:
            if c == 0xFF:
                break
            out += G3_CHARS.get(c, "?")
        return out
    anchors = []
    for name in ("Fennekin", "Pikachu", "Caterpie", "Eevee", "Vulpix"):
        enc = g3_encode(name, len(name)) + b"\xff"
        pos = 0
        while True:
            pos = rom.find(enc, pos)
            if pos == -1:
                break
            anchors.append(pos)
            pos += 1
    if not anchors:
        return []
    table = {}
    stride = 424
    for anchor in set(anchors):
        for direction in (-1, 1):
            o = anchor
            for _ in range(500):
                if not 0 <= o < len(rom) - 200:
                    break
                name = g3_decode(rom[o:o+20])
                if name and name in SPECIES:
                    sid = SPECIES.index(name)
                    g = rom[o + 186]
                    gr = rom[o + 189]
                    if 0 <= g <= 255 and 0 <= gr <= 5:
                        table[sid] = (g, gr)
                o += direction * stride
    if len(table) < 50:
        return []
    STATS_DIAG.append("lazarus 424-byte table, %d species" % len(table))
    return [(True, len(table), table)]


def find_base_stats(rom, idx_to_nat=None):
    """Find the hack's species data table and return
    {hack species number: (gender ratio, growth rate)}, or None.
    The table is found from the gender ratios of Pokemon #28-#35 (see NIDO_GENDERS),
    which sit one record apart; the record size comes from that, and where the
    growth rate is stored is worked out by matching official data. A search based
    on Bulbasaur's base stats is the fallback."""
    del STATS_DIAG[:]
    STATS_DIAG.append("size %d" % len(rom))
    found = _find_by_nidoran(rom, idx_to_nat) + _find_by_bulbasaur(rom, idx_to_nat)
    if not found:
        found = _find_by_names(rom, idx_to_nat)
    if not found:
        found = _find_lazarus(rom)
    return max(found, key=lambda f: f[:2])[2] if found else None


def _learn_field(rom, base, stride, pairs, field, offsets):
    """Find the byte (offset from base) that behaves like the official gender
    ratio (field 0) or growth rate (field 1) whatever its encoding: Pokemon with
    the same official value share one value there, different ones differ.
    -> (offset, {stored value: official value}) or None."""
    from collections import Counter
    results = []
    for k in offsets:
        by_official = {}
        for i, n in pairs:
            by_official.setdefault(UU[n][field], Counter())[rom[base + i * stride + k]] += 1
        if len(by_official) < 4:
            continue
        top = {off: c.most_common(1)[0] for off, c in by_official.items()}
        consistent = sum(cnt for _, cnt in top.values())
        values = [v for v, _ in top.values()]
        if len(set(values)) != len(values):       # two official values stored the same way
            continue
        results.append((consistent, k, {v: off for off, (v, _) in top.items()}))
    results.sort(key=lambda r: -r[0])
    if not results:
        STATS_DIAG.append("%s none" % "gr"[field])
        return None
    best = results[0]
    second = results[1][0] if len(results) > 1 else 0
    STATS_DIAG.append("%s %d:%d/%d/%d" % ("gr"[field], best[1], best[0], second, len(pairs)))
    if best[0] < 0.85 * len(pairs) or best[0] - second < 0.1 * len(pairs):
        return None
    return best[1], best[2]


def _find_by_names(rom, idx_to_nat):
    """pokeemerald-expansion keeps each Pokemon's name inside its record, so the
    distance between "Bulbasaur", "Ivysaur" and "Venusaur" is the record size."""
    out = []
    for case in (str, str.upper):
        names = [g3_encode(case(n), len(n)) + b"\xFF" for n in ("Bulbasaur", "Ivysaur", "Venusaur")]
        STATS_DIAG.append("%s x%d" % ("Bulbasaur" if case is str else "BULBASAUR", rom.count(names[0])))
        pos = rom.find(names[0])
        while pos != -1:
            for stride in range(24, MAX_RECORD + 1):
                if rom[pos + stride: pos + stride + len(names[1])] == names[1] and \
                        rom[pos + 2 * stride: pos + 2 * stride + len(names[2])] == names[2]:
                    base = pos - stride            # name position of record 0
                    STATS_DIAG.append("names %X/%d" % (base, stride))
                    table = _learned_table(rom, base, stride, idx_to_nat)
                    if table:
                        out.append((True, len(table), table))
            pos = rom.find(names[0], pos + 1)
    return out


def _learned_table(rom, base, stride, idx_to_nat):
    pairs = [(i, (idx_to_nat or {}).get(i, i if not idx_to_nat else None)) for i in range(1, 252)]
    pairs = [(i, n) for i, n in pairs if n and n <= 809]
    lo = max(-stride + 1, -base)
    if base + 253 * stride > len(rom):
        return None
    offsets = [k for k in range(lo, stride) if not 0 <= k < 13]      # skip the name itself
    g = _learn_field(rom, base, stride, pairs, 0, offsets)
    r = _learn_field(rom, base, stride, pairs, 1, offsets)
    if not g or not r:
        return None
    (gk, gmap), (rk, rmap) = g, r
    table = {}
    for i in range(1, 3000):
        o = base + i * stride
        if o + max(gk, rk) >= len(rom) or o + min(gk, rk) < 0:
            break
        gv, rv = rom[o + gk], rom[o + rk]
        name = rom[o:o + 13]
        named = 0xBB <= name[0] <= 0xEE and 0xFF in name          # a real record has a name
        if named and rv in rmap and gv in gmap:
            table[i] = (gmap[gv], rmap[rv])
    return table


def _nat_index(idx_to_nat, nat):
    if not idx_to_nat:
        return nat
    hits = [i for i, n in idx_to_nat.items() if n == nat]
    return hits[0] if hits else None


def _find_by_nidoran(rom, idx_to_nat):
    first = _nat_index(idx_to_nat, 28)
    if first is None or [_nat_index(idx_to_nat, n) for n in range(28, 36)] != list(range(first, first + 8)):
        return []
    import bisect
    fem = [m.start() for m in re.finditer(b"\xFE", rom)]
    hits, out, triples = 0, [], {}
    for a, p in enumerate(fem):                       # p = Nidoran-F's gender byte
        for q in fem[a + 1: bisect.bisect_right(fem, p + MAX_RECORD, a + 1)]:
            stride = q - p
            if stride < 24 or p - stride < 0 or p + 6 * stride >= len(rom):
                continue
            if rom[p + 2 * stride] == 0xFE:
                triples[stride] = triples.get(stride, 0) + 1
            if any(rom[p + (k - 1) * stride] != g for k, g in enumerate(NIDO_GENDERS)):
                continue
            hits += 1
            g0 = p - (first + 1) * stride             # gender byte of record 0
            STATS_DIAG.append("nido %X/%d" % (g0, stride))
            table = _read_stats_table(rom, g0, stride, idx_to_nat, gender_at=0)
            if table:
                used = any(struct.pack("<I", 0x08000000 + g0 - k) in rom for k in range(0, 0x40))
                out.append((used, len(table), table))
    top = sorted(triples.items(), key=lambda kv: -kv[1])[:3]
    STATS_DIAG.insert(1, "FE x%d, nido x%d, FE3 %s" % (len(fem), hits,
                                                      " ".join("%d:%d" % kv for kv in top) or "-"))
    return out


def _find_by_bulbasaur(rom, idx_to_nat):
    bulba, ivy, venu = BASE_STATS_START
    STATS_DIAG.append("stats x%d" % rom.count(bulba))
    out = []
    pos = rom.find(bulba)
    while pos != -1:
        for stride in range(24, MAX_RECORD + 1):
            if rom[pos + stride: pos + stride + 6] == ivy and \
                    (rom[pos + 2 * stride: pos + 2 * stride + 6] == venu[0] or
                     rom[pos + 3 * stride: pos + 3 * stride + 6] == venu[1]):
                start = pos - stride
                STATS_DIAG.append("table %X/%d" % (start, stride))
                table = _read_stats_table(rom, start, stride, idx_to_nat)
                if table:
                    # hacks that enlarge the table often leave the old copy behind, unused:
                    # prefer a table the game's code points to, then the biggest one
                    used = struct.pack("<I", 0x08000000 + start) in rom
                    out.append((used, len(table), table))
        pos = rom.find(bulba, pos + 1)
    return out


def _read_stats_table(rom, start, stride, idx_to_nat, gender_at=None):
    pairs = [(i, (idx_to_nat or {}).get(i, i if not idx_to_nat else None)) for i in range(1, 252)]
    pairs = [(i, n) for i, n in pairs if n and n <= 809]
    if start < 0 or start + 253 * stride > len(rom):
        return None
    best = {}
    for field in (0, 1):                       # 0 = gender ratio, 1 = growth rate
        scores = []
        if gender_at is None:                  # start = record start: try every byte
            offsets = range(6, stride)
        elif field == 0:
            offsets = [gender_at, None]
        else:                                  # start = gender byte: try bytes around it
            offsets = range(max(-start, -min(stride - 1, 64)), min(stride, 64))
        for k in offsets:
            if k is None:
                scores.append((0, -999))
                continue
            hits = sum(1 for i, n in pairs if rom[start + i * stride + k] == UU[n][field])
            scores.append((hits, k))
        scores.sort(reverse=True)
        (hits, k), (second, _) = scores[0], scores[1]
        STATS_DIAG.append("%s %d:%d/%d/%d" % ("gr"[field], k, hits, second, len(pairs)))
        if hits < 0.7 * len(pairs) or hits - second < 0.2 * len(pairs):
            return None
        best[field] = k
    g, r = best[0], best[1]
    count = (len(rom) - start) // stride
    table = {}
    for i in range(1, min(count, 3000)):
        o = start + i * stride
        if o + max(g, r) >= len(rom):
            break
        rate = rom[o + r]
        if rate > 5:                           # past the end of the table
            break
        table[i] = (rom[o + g], rate)
    return table


def stats_agreement(stats, idx_to_nat=None):
    """How many Gen 1-2 Pokemon have the official gender ratio and growth rate in
    the ROM data: (matching, compared). Real hacks change only a few."""
    agree = total = 0
    for i in range(1, 252):
        n = (idx_to_nat or {}).get(i, i if not idx_to_nat else None)
        if n and n <= 809 and i in stats:
            total += 1
            agree += tuple(stats[i]) == (UU[n][0], UU[n][1])
    return agree, total


class RomTables:
    """Data read from a hack's ROM file: the species data table (gender odds and
    level-up rates the hack really uses) and, for hacks that reuse Pokemon
    numbers, the Pokemon and move name lists."""

    def __init__(self, path, need_names=False):
        try:
            with open(path, "rb") as f:
                rom = f.read()
        except OSError as e:
            raise ExportError("Couldn't open the ROM file:\n%s" % e)
        sp = read_name_table(rom, b"\xAC" * 10 + b"\xFF", g3_encode("BULBASAUR", 9) + b"\xFF",
                             11, 1500)
        mv = read_name_table(rom, b"\xAE" * 7 + b"\xFF", g3_encode("POUND", 5) + b"\xFF",
                             13, 1000)
        self.species = {i: name_to_id(n, SPECIES_BY_NAME) for i, n in enumerate(sp or [])}
        self.species_names = dict(enumerate(sp or []))
        self.moves = {i: name_to_id(n, MOVES_BY_NAME, MOVE_ALIASES) for i, n in enumerate(mv or [])}
        self.stats = find_base_stats(rom, self.species if (need_names and sp) else None)
        self.rejected = None
        if self.stats:
            agree, total = stats_agreement(self.stats, self.species if (need_names and sp) else None)
            if total < 50 or agree < 0.75 * total:
                # a real hack changes a few Pokemon; mostly-different data means it was misread
                self.rejected = (agree, total)
                self.stats = None
        if (need_names and not sp) or not (sp or self.stats):
            raise ExportError("Couldn't find the Pokémon data in this file.\n"
                              "Make sure it's the patched ROM (.gba) of the hack you're playing.\n\n"
                              "Details (for a bug report): " + "; ".join(STATS_DIAG[:8]))
        if self.rejected and not sp:
            raise ExportError("The Pokémon data found in this ROM doesn't look right (only %d of %d "
                              "Pokémon match the official games), so it can't be used.\n\n"
                              "You can still set a Pokémon's gender or level by clicking it in the list.\n\n"
                              "Details (for a bug report): %s" % (self.rejected + ("; ".join(STATS_DIAG[:8]),)))
        parts = []
        if need_names:
            parts.append("%d Pokémon names and %d move names" % (len(sp), len(mv or [])))
        if self.stats:
            parts.append("the gender odds and level-up rates of %d Pokémon" % len(self.stats))
        self.summary = "Read %s from the ROM." % " and ".join(parts)


class Gen3StyleProfile(Profile):
    """Hacks that keep the original Gen 3 Pokemon format."""
    party_offsets = (0x234, 0x238)     # Ruby/Sapphire/Emerald (FireRed: 0x34, 0x38)
    encrypted = True
    storage = None                     # (first, last) sector of the PC boxes, if known
    storage_stride = None              # bytes of PC data per sector (default: the save's)

    def species(self, sid, m=None):
        nat = g3_species_to_national(sid)
        return (nat, "base", "") if nat else None

    def move(self, mid):
        return mid if 0 < mid <= 354 else None

    def ball(self, b):
        return b if 1 <= b <= 12 else 4

    def decode(self, b, party):
        return decode_gen3(b, party, self.encrypted)

    def party(self, save):
        cnt_at, at = self.party_offsets
        count = struct.unpack_from("<I", save.secs[1], cnt_at)[0]
        if not 0 <= count <= 6:
            return None
        return [self.decode(save.secs[1][at + i * 100: at + (i + 1) * 100], True)
                for i in range(count)]

    def read(self, save):
        out = [("Party %d" % (i + 1), True, m) for i, m in enumerate(self.party(save)) if m]
        if self.storage:
            if self.storage_stride:
                pc = b"".join(save.secs[k][:self.storage_stride]
                              for k in range(self.storage[0], self.storage[1] + 1))
            else:
                pc = save.joined(*self.storage)
            names_at = 4 + 420 * 80
            for box in range(14):
                name = g3_decode(pc[names_at + box * 9: names_at + box * 9 + 9]) or "Box %d" % (box + 1)
                for slot in range(30):
                    o = 4 + (box * 30 + slot) * 80
                    m = self.decode(pc[o:o + 80], False)
                    if m:
                        out.append(("%s, slot %d" % (name, slot + 1), False, m))
        return g3_decode(save.secs[0][0:8]), out


class OdysseyProfile(Gen3StyleProfile):
    """Pokemon Odyssey (FireRed base). Pokemon use the original Gen 3 format,
    but are stored unencrypted, unshuffled and without a checksum."""
    name, short = "Pokémon Odyssey (v4.1)", "Odyssey"
    custom_abilities = True
    party_offsets = (0x34, 0x38)
    encrypted = False
    storage, storage_stride = (5, 13), 0xFF0     # PC data uses 4080 bytes of each sector

    def move(self, mid):
        return mid if 0 < mid <= 621 else None

    def detect(self, save):
        if save.count != 14 or struct.unpack_from("<I", save.secs[0], 0xAC)[0] != 1 or \
                save.signature != SIGNATURES[0]:
            return False                      # FireRed/LeafGreen-style save only
        cnt_at, at = self.party_offsets
        count = struct.unpack_from("<I", save.secs[1], cnt_at)[0]
        if not 1 <= count <= 6:
            return False
        for i in range(count):
            b = save.secs[1][at + i * 100: at + (i + 1) * 100]
            if struct.unpack_from("<H", b, 0x1C)[0] != 0:   # vanilla FRLG stores a checksum
                return False
            m = self.decode(b, True)
            if m is None or not m["checksum_ok"]:
                return False
        return True


# Poke Ball order used by CFRU's compact PC format -> official ball IDs
CFRU_BALLS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 4, 17, 18, 19, 20, 21, 22,
              23, 4, 26, 25]


def decode_cfru58(b):
    """The compact 58-byte PC format of CFRU hacks (Unbound, Radical Red...)."""
    pid, tid, sid = struct.unpack_from("<IHH", b, 0)
    species = struct.unpack_from("<H", b, 0x1C)[0]
    if species == 0 or tid == 0 and pid == 0:
        return None
    m = {"pid": pid, "otid": tid | (sid << 16), "nick_raw": bytes(b[8:18]), "lang": b[0x12] & 7,
         "hidden_nature": 0, "bad_egg": False, "ot_raw": bytes(b[0x14:0x1B]),
         "markings": b[0x1B] & 0xF, "shiny_flag": False, "species_id": species,
         "item": struct.unpack_from("<H", b, 0x1E)[0], "exp": struct.unpack_from("<I", b, 0x20)[0],
         "pp_ups": b[0x24], "friendship": b[0x25], "hyper": [False] * 6,
         "contest": [0] * 6, "ribbons": 0, "fateful": 0, "level": None}
    ball = b[0x26]
    m["ball_cfru"] = CFRU_BALLS[ball] if ball < len(CFRU_BALLS) else 4
    bits = int.from_bytes(b[0x27:0x2C], "little")
    m["moves_raw"] = [(bits >> (10 * i)) & 0x3FF for i in range(4)]
    m["pp"] = None            # not stored; filled in from the moves' base PP
    m["evs"] = list(b[0x2C:0x32])
    m["pokerus"] = b[0x32]
    org = struct.unpack_from("<H", b, 0x34)[0]
    m["met_level"], m["game"], m["ot_gender"] = org & 0x7F, (org >> 7) & 0xF, org >> 15
    m["ball_raw"] = 0
    iv = struct.unpack_from("<I", b, 0x36)[0]
    m["ivs"] = [(iv >> (5 * i)) & 31 for i in range(6)]
    m["egg"] = bool(iv & 0x40000000)
    m["ability_num"] = 2 if iv >> 31 else pid & 1
    m["checksum_ok"] = m["exp"] < 2000000
    return m


class DpeProfile(Gen3StyleProfile):
    """FireRed hacks using the Dynamic Pokemon Expansion numbering (Gen 4+ Pokemon
    added after the Gen 3 ones). Party Pokemon are stored unencrypted. In these
    hacks the ability bit means "Hidden Ability"; otherwise the personality value
    decides between the first and second ability."""
    party_offsets = (0x34, 0x38)
    encrypted = False
    custom_abilities = True

    def species(self, sid, m=None):
        d = DPE.get(str(sid))
        if not d:
            return None
        nat, form, kind, label = d
        if kind == "battle":
            kind, form = "base", 0
        return nat, kind, label, form

    def move(self, mid):
        return CFRUMOVES[mid] if 0 < mid < len(CFRUMOVES) else None

    def ball(self, b):
        return b if 1 <= b <= 12 else 4

    def decode(self, b, party):
        m = decode_gen3(b, party, False)
        if m:
            m["ability_num"] = 2 if m["ability_num"] else m["pid"] & 1
        return m


class GaiaProfile(DpeProfile):
    name, short = "Pokémon Gaia (v3.2)", "Gaia"
    storage, storage_stride = (5, 13), 0xFF0

    def ball(self, b):
        return 4      # Gaia's ball numbering isn't confirmed yet: use a Poké Ball

    def detect(self, save):
        return OdysseyProfile.detect(self, save) and all(
            self.species(m["species_id"]) for m in self.party(save) if m)


class UnboundProfile(DpeProfile):
    """Pokemon Unbound: its own save signature; PC boxes in CFRU's compact format."""
    name, short = "Pokémon Unbound (v2.1)", "Unbound"
    boxes = 18

    def detect(self, save):
        return save.signature in SIGNATURES[1:]

    def read(self, save):
        out = [("Party %d" % (i + 1), True, m) for i, m in enumerate(self.party(save)) if m]
        pc = b"".join(save.secs[k][:0xFF0] for k in range(5, 14))
        for i in range(self.boxes * 30):
            o = 4 + i * 58
            if o + 58 > len(pc):
                break
            m = decode_cfru58(pc[o:o + 58])
            if m:
                out.append(("Box %d, slot %d" % (i // 30 + 1, i % 30 + 1), False, m))
        return g3_decode(save.secs[0][0:8]), out


class LightPlatinumProfile(Gen3StyleProfile):
    """Pokemon Light Platinum (Ruby base). Original Gen 3 format, but many old
    Pokemon numbers were reused for Gen 4 Pokemon, so species are identified
    from the ROM's name list (or, without the ROM, from unchanged nicknames)."""
    name, short = "Pokémon Light Platinum", "Light Platinum"
    custom_abilities = True
    storage = (5, 13)
    needs_rom = True

    def __init__(self):
        self.rom = None

    def species(self, sid, m=None):
        if self.rom:
            nat = self.rom.species.get(sid)
            if nat is None and sid in self.rom.species_names:
                if m is not None:
                    m["species_note"] = "its species in the ROM (%s) has no official match" \
                        % self.rom.species_names[sid]
            return (nat, "base", "") if nat else None
        if m is not None:     # no ROM: a Pokemon that was never nicknamed carries its species name
            nat = SPECIES_BY_NAME.get(_norm(g3_decode(m["nick_raw"])))
            if nat:
                m["species_note"] = ("identified from its name — load your Light Platinum ROM "
                                     "(\"Load ROM…\") to be certain")
                return nat, "base", ""
        return None

    def move(self, mid):
        if self.rom and self.rom.moves:
            return self.rom.moves.get(mid)
        return mid if 0 < mid <= 354 else None

    def detect(self, save):
        if save.count != 14 or save.data_size != 3968 or save.signature != SIGNATURES[0] or \
                struct.unpack_from("<I", save.secs[0], 0xAC)[0] != 0:
            return False
        mons = self.party(save)
        if not mons or any(m is None or not m["checksum_ok"] for m in mons):
            return False
        return all(m["game"] in (1, 2) for m in mons if not m["egg"])   # Sapphire / Ruby


PROFILES = [LazarusProfile(), ImperiumProfile(), UnboundProfile(), OdysseyProfile(), GaiaProfile(),
            LightPlatinumProfile()]


# =============================================================== conversion
def calc_stats(base, ivs, evs, level, nature):
    """Stats in save order HP Atk Def Spe SpA SpD (all lists in that order)."""
    out = [(2 * base[0] + ivs[0] + evs[0] // 4) * level // 100 + level + 10]
    up, down = nature // 5, nature % 5             # nature order: Atk Def Spe SpA SpD
    for i in range(1, 6):
        v = (2 * base[i] + ivs[i] + evs[i] // 4) * level // 100 + 5
        k = i - 1
        out.append(v * 11 // 10 if k == up != down else v * 9 // 10 if k == down != up else v)
    return out


def gender_from_ratio(pid, ratio):
    """Gen 3 rule: 0 male, 1 female, 2 genderless."""
    if ratio == 255:
        return 2
    if ratio in (0, 254):
        return 0 if ratio == 0 else 1
    return int((pid & 0xFF) < ratio)


def reroll_pid(pid, otid, want, ratio, shiny):
    """A new personality value with the wanted gender (official odds), the same
    nature and the same shininess. In Gen 3 files gender comes from this value."""
    nature, tsv = pid % 25, (otid & 0xFFFF) ^ (otid >> 16)
    lows = [g for g in range(256) if int(g < ratio) == want]
    lows.sort(key=lambda g: ((g & 1) != (pid & 1), abs(g - (pid & 0xFF))))
    for g in lows:
        if shiny:
            for b in range(256):
                lo = (b << 8) | g
                for x in range(8):
                    cand = ((lo ^ tsv ^ x) << 16) | lo
                    if cand % 25 == nature:
                        return cand
        else:
            base = (pid & 0xFFFFFF00) | g
            for k in range(-200, 200):
                cand = base + k * 256
                if 0 <= cand <= 0xFFFFFFFF and cand % 25 == nature:
                    v = tsv ^ (cand & 0xFFFF) ^ (cand >> 16)
                    if v >= 8:
                        return cand
    return pid


class Entry:
    """One Pokemon from a save, plus everything worked out for exporting it."""

    def __init__(self, where, party, mon, profile, keep_balls=False, gender=None, level=None):
        self.where, self.party, self.m, self.profile = where, party, mon, profile
        self.keep_balls = keep_balls
        self.set_gender, self.set_level = gender, level      # set by the user to match the game
        self.gender_unsure = False
        self.notes, self.blocker = [], None
        self.format = None
        self._plan()

    @property
    def exportable(self):
        return self.blocker is None

    def _plan(self):
        m, prof = self.m, self.profile
        self.name, self.level = "Pokémon #%d" % m["species_id"], m["level"]
        if not m["checksum_ok"] or m["bad_egg"]:
            self.blocker = "data is corrupted"
            return
        if m["egg"]:
            self.name, self.blocker = "Egg", "Eggs are skipped"
            return
        m.pop("species_note", None)
        sp = prof.species(m["species_id"], m)
        if m.get("species_note"):
            self.notes.append(m["species_note"])
        if sp is None:
            if prof.needs_rom and not prof.rom:
                self.blocker = ("can't tell which Pokémon this is (ID %d) — load the hack's ROM "
                                "with \"Load ROM…\" to identify it" % m["species_id"])
            else:
                self.blocker = ("unrecognised species (ID %d) - probably a hack-exclusive "
                                "Pokémon or form" % m["species_id"])
            return
        nat, kind, suffix = sp[:3]
        formnum = sp[3] if len(sp) > 3 else None
        self.nat, self.form, self.name = nat, 0, SPECIES[nat]
        need = {"species": gen_of_species(nat)}
        if kind == "alola":
            self.form, self.name = 1, self.name + " (Alolan)"
            need["Alolan form"] = 7
        elif kind in ("galar", "hisui", "paldea"):
            label = {"galar": "Galarian", "hisui": "Hisuian", "paldea": "Paldean"}[kind]
            self.form = formnum or 1
            if nat == 555 and self.form == 3:      # Galarian Darmanitan's Zen Mode only exists in battle
                self.form = 2
            self.name += " (%s)" % label
            need[label + " form"] = 9 if kind == "paldea" else 8
        elif kind == "form":
            self.notes.append("its alternate form (%s) isn't supported yet - exported as the "
                              "regular form" % suffix.replace("_", " ").title())
        # moves
        self.moves, self.pp, self.pp_ups = [], [], []
        for i, raw in enumerate(m["moves_raw"]):
            if raw == 0:
                continue
            mv = prof.move(raw)
            if mv is None:
                self.notes.append("dropped a move the program doesn't recognise (ID %d)" % raw)
                continue
            self.moves.append(mv)
            self.pp.append(m["pp"][i] if m["pp"] is not None else (BASE_PP[mv] if mv < len(BASE_PP) and BASE_PP[mv] else 10))
            self.pp_ups.append((m["pp_ups"] >> (2 * i)) & 3)
            need["move " + MOVES[mv]] = gen_of_move(mv)
        # nickname
        nick = g3_decode(m["nick_raw"])
        self.nicknamed = nick.lower() != SPECIES[nat].lower()
        self.nickname = nick if self.nicknamed else SPECIES[nat]
        if self.nicknamed and len(nick) > 10:
            need["12-letter nickname"] = 4
        # ability: the slot is read from the save, its meaning from official data
        self.ability_num = m["ability_num"]
        bd = base_data(nat, self.form, 7)
        if bd:
            self.ability, self.ability_number = self._slot_ability(bd)
            if self.ability_number == 4:
                need["Hidden Ability"] = 5
            slot = {1: 0, 2: 1, 4: 2}[self.ability_number]
            if self.form == 0 and nat <= 386 and self.ability in G3AB[nat]:
                self.g3_ability_bit = G3AB[nat].index(self.ability)
            elif self.form == 0 and nat <= 721 and AO[nat][2 + slot] == self.ability:
                need["ability " + ABILITIES[self.ability]] = max(4, need.get("Hidden Ability", 4))
            elif self.ability:
                need["ability " + ABILITIES[self.ability]] = \
                    7 if self.ability <= 233 else 8 if self.ability <= 267 else 9
        else:
            self.ability = None
        # Poke Ball: only counts toward the format if the user wants original balls kept
        self.ball = m["ball_cfru"] if "ball_cfru" in m else prof.ball(m["ball_raw"])
        if self.keep_balls and self.ball != 4:
            need["%s Ball" % OFFICIAL_BALLS.get(self.ball, "?")] = gen_of_ball(self.ball)
        # what the hack itself says about level and gender (from the save, or the hack's ROM)
        hack = prof.rom.stats.get(m["species_id"]) if prof.rom and getattr(prof.rom, "stats", None) else None
        if self.level is None and hack:
            self.level = level_for_exp(hack[1], m["exp"])
        self.hack_gender = gender_from_ratio(m["pid"], hack[0]) if hack else None
        known = prof.known_genders.get(m["species_id"])
        if self.hack_gender is None and known is not None:
            self.hack_gender = gender_from_ratio(m["pid"], known)
        # gender we can't be sure of: the hack changes gender odds and we don't have its data
        self.gender_unsure = bool(prof.check_genders and not hack and known is None
                                  and self.set_gender is None)
        if self.set_level:
            self.level = self.set_level
            self.notes.append("level set to %d by you" % self.level)
        if self.set_gender is not None:
            self.hack_gender = self.set_gender
            self.notes.append("gender set to %s by you" % ("male", "female")[self.set_gender])
        # format
        self.need = need
        gen = max(need.values())
        if gen <= 7:
            self.format = 3 if gen <= 3 else 6 if gen <= 6 else 7
        elif not self._choose_gen8_format(gen):
            if self.level is None and bd:
                self.level = level_for_exp(bd[1], m["exp"])
            return
        self.reason = max(self.need.items(), key=lambda kv: kv[1])
        self.min_gen = max(3, max(self.need.values()))     # oldest game generation it can go to
        if self.format >= 8:
            self.ability, self.ability_number = self._slot_ability(base_data(nat, self.form, self.format))
        # level / EXP on the official curve
        official = base_data(nat, self.form, self.format)
        group = G3GROW[nat] if self.format == 3 else official[1]
        self.exp = m["exp"]
        if self.level is None:
            self.level = level_for_exp(group, self.exp)
        elif level_for_exp(group, self.exp) != self.level:
            self.exp = exp_for_level(group, self.level)
            self.notes.append("EXP adjusted so it stays Lv. %d on the official EXP curve" % self.level)
        # gender
        self.pid = m["pid"]
        ratio = UU[nat][0] if self.format == 3 else official[0]
        self.gender = gender_from_ratio(self.pid, ratio)
        self.gender_unsure = self.gender_unsure and ratio not in (0, 254, 255)
        want = self.hack_gender
        if want is not None and want != self.gender:
            sexes = ("male", "female", "genderless")
            if ratio in (0, 254, 255) or want == 2:
                self.notes.append("it's %s in the hack, but official %s are always %s - exported as %s"
                                  % (sexes[want], SPECIES[nat], sexes[self.gender], sexes[self.gender]))
            elif self.format == 3:
                self.pid = reroll_pid(self.pid, m["otid"], want, ratio, self.shiny(8))
                self.gender = want
                self.notes.append("personality value adjusted so it's %s in official games too; "
                                  "nature and shininess unchanged" % sexes[want])
            else:
                self.gender = want
        # ball
        limit = BALL_LIMIT[self.format]
        if self.ball > limit:
            self.notes.append("%s Ball doesn't exist in Gen %d - changed to a Poké Ball"
                              % (OFFICIAL_BALLS.get(self.ball, "That"), self.format))
            self.ball = 4
        # other things that can't be stored
        if m["hidden_nature"]:
            self.notes.append("its nature was changed with a mint, which these formats can't store "
                              "- it keeps its original nature (%s)" % NATURES[m["pid"] % 25])
        if any(m["hyper"]) and self.format < 7:
            self.notes.append("Hyper Training can't be stored before Gen 7 - dropped")
        if m["shiny_flag"] and not self.shiny(8):
            self.notes.append("the hack made it shiny with a special flag that official games "
                              "don't have - it won't be shiny after transfer")
        if self.format > 3 and self.shiny(16) and not self.shiny(8):
            self.notes.append("its personality value counts as shiny in Gen 6+ games, so it will "
                              "appear shiny there")

    def _slot_ability(self, bd):
        """(ability, official ability number 1/2/4) for the save's ability slot."""
        a1, a2, ah = bd[2:5]
        num = self.ability_num
        if num == 2 and ah:
            return ah, 4
        if num == 1 and a2 and a2 != a1:
            return a2, 2
        return a1, 1

    def _choose_gen8_format(self, gen):
        """Pick .pk8 (Sword/Shield) or .pk9 (Scarlet/Violet) for a Pokemon that needs
        Gen 8+ data: the game must have the Pokemon; moves that game can't use are
        dropped, so the game that keeps more moves wins (Sword/Shield on a tie)."""
        options = []
        for fmt in ((8, 9) if gen == 8 else (9,)):
            e = game_entry(fmt, self.nat, self.form)
            if not e or not e[0]:
                continue
            _, _, unusable, last = GAMES[fmt]
            bad = [mv for mv in self.moves if mv > last or mv in unusable]
            options.append((len(bad), fmt, bad))
        if not options:
            games = " or ".join(GAMES[f][0] for f in ((8, 9) if gen == 8 else (9,)))
            self.blocker = "%s isn't in %s, so it can't be exported yet" % (self.name, games)
            return False
        _, self.format, bad = min(options)
        if self.format == 9 and gen == 8:
            in8 = any(f == 8 for _, f, _ in options)
            self.need["keeps more moves in Scarlet/Violet" if in8 else "not in Sword/Shield"] = 9
        for mv in bad:
            i = self.moves.index(mv)
            del self.moves[i], self.pp[i], self.pp_ups[i]
            self.need.pop("move " + MOVES[mv], None)
            self.notes.append("%s can't be used in %s - dropped" % (MOVES[mv], GAMES[self.format][0]))
        return True

    def shiny(self, threshold):
        m = self.m
        v = (m["otid"] & 0xFFFF) ^ (m["otid"] >> 16) ^ (m["pid"] & 0xFFFF) ^ (m["pid"] >> 16)
        return v < threshold

    def summary(self):
        """Multi-line description for the details panel / text mode."""
        m = self.m
        lines = ["%s — %s" % (self.name if not getattr(self, "nicknamed", False)
                               else "%s (%s)" % (self.nickname, self.name), self.where)]
        if self.blocker:
            lines.append("Can't export: " + self.blocker)
        if hasattr(self, "moves"):
            sex = getattr(self, "gender", getattr(self, "hack_gender", None))
            lines.append("Lv. %s   %s   %s nature   %s" % (
                self.level or "?", {0: "♂", 1: "♀", 2: "genderless"}.get(sex, "")
                + ("?" if self.exportable and self.gender_unsure else ""), NATURES[m["pid"] % 25],
                ABILITIES[self.ability] if self.ability else ""))
            if self.exportable and self.gender_unsure:
                lines.append("? %s can change gender odds, so this gender may not match the game. "
                             "Check its summary screen and click ♂/♀ to change it if needed."
                             % self.profile.short)
            lines.append("Moves: " + (", ".join(MOVES[x] for x in self.moves) or "none"))
            st = ["HP", "Atk", "Def", "Spe", "SpA", "SpD"]
            lines.append("IVs: " + "  ".join("%s %d" % (s, v) for s, v in zip(st, m["ivs"])))
            lines.append("EVs: " + "  ".join("%s %d" % (s, v) for s, v in zip(st, m["evs"])))
            lines.append("OT: %s  ID %05d   %s Ball%s" % (
                g3_decode(m["ot_raw"]), m["otid"] & 0xFFFF,
                OFFICIAL_BALLS.get(getattr(self, "ball", self.profile.ball(m["ball_raw"])), "?"),
                "   ★ shiny" if self.shiny(8) else ""))
        if self.format and self.format >= 8:
            lines.append("Can go to %s (Gen %d) and newer games (because of: %s, Gen %d) — exports as .pk%d"
                         % ((GAMES[self.format][0], self.format) + self.reason + (self.format,)))
        elif self.format:
            if self.min_gen > 3:
                lines.append("Can go to Gen %d and newer games (because of: %s, Gen %d) — exports as .pk%d"
                             % ((self.min_gen,) + self.reason + (self.format,)))
            else:
                lines.append("Can go to Gen 3 and newer games — exports as .pk3")
        if self.format:
            if self.profile.custom_abilities and self.ability:
                lines.append("• %s changes some Pokémon's abilities. This one gets the official ability "
                             "for the same slot (%s)." % (self.profile.short, ABILITIES[self.ability]))
        for n in self.notes:
            lines.append("• " + n)
        return "\n".join(lines)

    # ------------------------------------------------------------ writers
    def build(self):
        if self.format == 3:
            return self._pk3()
        return self._pk67(self.format) if self.format <= 7 else self._pk89(self.format)

    def _pk3(self):
        m, nat = self.m, self.nat
        d = bytearray(80)
        struct.pack_into("<II", d, 0, self.pid, m["otid"])
        d[0x08:0x12] = m["nick_raw"][:10] if self.nicknamed else g3_encode(SPECIES[nat].upper(), 10)
        d[0x12], d[0x13] = m["lang"] or 2, 0x02
        d[0x14:0x1B], d[0x1B] = m["ot_raw"], m["markings"]
        ppups = sum(u << (2 * i) for i, u in enumerate(self.pp_ups))
        struct.pack_into("<HHIBB", d, 0x20, G3INT[nat], 0, self.exp, ppups, m["friendship"])
        for i, mv in enumerate(self.moves):
            struct.pack_into("<H", d, 0x2C + 2 * i, mv)
            d[0x34 + i] = self.pp[i]
        d[0x38:0x3E], d[0x3E:0x44] = bytes(m["evs"]), bytes(m["contest"])
        d[0x44], d[0x45] = m["pokerus"], 254                 # 254 = obtained in a trade
        struct.pack_into("<H", d, 0x46, (m["met_level"] & 0x7F) | (3 << 7) | (self.ball << 11)
                         | (m["ot_gender"] << 15))         # origin game 3 = Emerald
        iv32 = sum(v << (5 * i) for i, v in enumerate(m["ivs"]))
        iv32 |= getattr(self, "g3_ability_bit", 0) << 31
        struct.pack_into("<II", d, 0x48, iv32, m["ribbons"] | (m["fateful"] << 31))
        struct.pack_into("<H", d, 0x1C, sum(struct.unpack_from("<24H", d, 0x20)) & 0xFFFF)
        return bytes(d)

    def _pk67(self, fmt):
        m, nat, gender = self.m, self.nat, self.gender
        d = bytearray(232)
        struct.pack_into("<I", d, 0x00, m["pid"])                 # encryption constant
        struct.pack_into("<HHII", d, 0x08, nat, 0, m["otid"], self.exp)
        d[0x14], d[0x15] = self.ability, self.ability_number
        struct.pack_into("<I", d, 0x18, m["pid"])
        d[0x1C] = m["pid"] % 25
        d[0x1D] = (m["fateful"] & 1) | (gender << 1) | (self.form << 3)
        d[0x1E:0x24], d[0x24:0x2A] = bytes(m["evs"]), bytes(m["contest"])
        if fmt == 6:
            d[0x2A] = m["markings"]
        else:
            struct.pack_into("<H", d, 0x16, sum(1 << (2 * i) for i in range(4) if m["markings"] >> i & 1))
        d[0x2B] = m["pokerus"]
        d[0x40:0x5A] = g6_encode(self.nickname)
        for i, mv in enumerate(self.moves):
            struct.pack_into("<H", d, 0x5A + 2 * i, mv)
            d[0x62 + i], d[0x66 + i] = self.pp[i], self.pp_ups[i]
        iv32 = sum(v << (5 * i) for i, v in enumerate(m["ivs"])) | (int(self.nicknamed) << 31)
        struct.pack_into("<I", d, 0x74, iv32)
        d[0xB0:0xCA] = g6_encode(g3_decode(m["ot_raw"]))
        d[0xCA] = m["friendship"]
        today = datetime.date.today()
        d[0xD4], d[0xD5], d[0xD6] = today.year - 2000, today.month, today.day
        struct.pack_into("<H", d, 0xDA, 30002)                   # met location: Link Trade
        d[0xDC] = self.ball
        d[0xDD] = (m["met_level"] & 0x7F) | (m["ot_gender"] << 7)
        if fmt == 7:   # Hyper Training flags, official order HP Atk Def SpA SpD Spe
            h = m["hyper"]
            d[0xDE] = sum(1 << i for i, on in enumerate((h[0], h[1], h[2], h[4], h[5], h[3])) if on)
        d[0xDF] = 26 if fmt == 6 else 32                         # Alpha Sapphire / Ultra Sun
        d[0xE0], d[0xE2], d[0xE3] = 49, 1, m["lang"] or 2        # USA, Americas region, language
        struct.pack_into("<H", d, 0x06, sum(struct.unpack_from("<112H", d, 8)) & 0xFFFF)
        return bytes(d)

    def _pk89(self, fmt):
        """Sword/Shield (.pk8) or Scarlet/Violet (.pk9), 344-byte party format
        (328 bytes of data plus level and stats, which OpenHome expects)."""
        m, nat = self.m, self.nat
        d = bytearray(0x158)
        struct.pack_into("<I", d, 0x00, m["pid"])                 # encryption constant
        species = nat if fmt == 8 else G9INT.get(str(nat), nat)    # Gen 9 renumbered some species
        struct.pack_into("<HHII", d, 0x08, species, 0, m["otid"], self.exp)
        struct.pack_into("<H", d, 0x14, self.ability)
        d[0x16] = self.ability_number
        struct.pack_into("<H", d, 0x18, sum(1 << (2 * i) for i in range(4) if m["markings"] >> i & 1))
        struct.pack_into("<I", d, 0x1C, m["pid"])
        d[0x20] = d[0x21] = m["pid"] % 25                          # nature, stat nature
        d[0x22] = (m["fateful"] & 1) | (self.gender << (2 if fmt == 8 else 1))
        struct.pack_into("<H", d, 0x24, self.form)
        d[0x26:0x2C], d[0x2C:0x32] = bytes(m["evs"]), bytes(m["contest"])
        d[0x32] = m["pokerus"]
        if fmt == 8:
            d[0x50] = d[0x51] = 0x80                               # height / weight
        else:
            d[0x48] = d[0x49] = d[0x4A] = 0x80                     # height / weight / scale
        d[0x58:0x72] = g6_encode(self.nickname)
        for i, mv in enumerate(self.moves):
            struct.pack_into("<H", d, 0x72 + 2 * i, mv)
            d[0x7A + i], d[0x7E + i] = self.pp[i], self.pp_ups[i]
        iv32 = sum(v << (5 * i) for i, v in enumerate(m["ivs"])) | (int(self.nicknamed) << 31)
        struct.pack_into("<I", d, 0x8C, iv32)
        lang = m["lang"] or 2
        if fmt == 8:
            d[0xDE], d[0xE2] = 44, lang                            # Sword, language
        else:
            d[0x94] = game_entry(9, nat, self.form)[6]             # Tera Type = first type
            d[0x95] = 19                                           # no Tera Type override
            d[0xCE], d[0xD5] = 50, lang                            # Scarlet, language
            d[0x11F] = m["met_level"] & 0x7F                       # obedience level
        d[0xF8:0x112] = g6_encode(g3_decode(m["ot_raw"]))
        d[0x112] = m["friendship"]
        today = datetime.date.today()
        d[0x11C], d[0x11D], d[0x11E] = today.year - 2000, today.month, today.day
        struct.pack_into("<H", d, 0x122, 30002)                  # met location: Link Trade
        d[0x124] = self.ball
        d[0x125] = (m["met_level"] & 0x7F) | (m["ot_gender"] << 7)
        h = m["hyper"]       # Hyper Training flags, official order HP Atk Def SpA SpD Spe
        d[0x126] = sum(1 << i for i, on in enumerate((h[0], h[1], h[2], h[4], h[5], h[3])) if on)
        struct.pack_into("<H", d, 0x06, sum(struct.unpack_from("<160H", d, 8)) & 0xFFFF)
        # party data (not covered by the checksum): level and stats
        stats = calc_stats(game_entry(fmt, nat, self.form)[7:13], m["ivs"], m["evs"],
                           self.level, m["pid"] % 25)
        d[0x148] = self.level
        struct.pack_into("<6H", d, 0x14A, *stats)
        struct.pack_into("<H", d, 0x8A, stats[0])                 # current HP = full
        return bytes(d)

    def filename(self):
        safe = lambda s: "".join(ch for ch in s if ch not in '<>:"/\\|?*').strip()
        where = self.where.replace(", slot ", "-")
        nick = " (%s)" % safe(self.nickname) if self.nicknamed else ""
        return "%s - %s%s.pk%d" % (safe(where), safe(self.name), nick, self.format)


def open_save(path, pick=None):
    """-> (profile, trainer name, [(location, is_party, decoded mon)]).
    Some hacks can't be told apart from the save alone; then pick(list of
    profiles) is asked to choose (returning None cancels)."""
    save = read_gba_save(path)
    matches = [p for p in PROFILES if p.detect(save)]
    if matches:
        prof = matches[0]
        if len(matches) > 1 and pick:
            prof = pick(matches)
            if prof is None:
                raise ExportError("Cancelled.")
        trainer, mons = prof.read(save)
        return prof, trainer, mons
    raise ExportError("This save isn't from a supported ROM hack.\nSupported: " +
                      ", ".join(p.name for p in PROFILES))


def export(entries, folder):
    os.makedirs(folder, exist_ok=True)
    written = []
    for e in entries:
        path = os.path.join(folder, e.filename())
        with open(path, "wb") as f:
            f.write(e.build())
        written.append(path)
    return written


def open_folder(folder):
    try:
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])
    except Exception:
        pass


# =============================================================== window (tkinter)
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".pokemon_hack_porter.json")
PALETTES = {
    False: dict(bg=None, panel="#ffffff", fg="#000000", muted="#666666", blocked="#999999",
                party="#eef5ff", border="#a0a0a0", select=None),
    True: dict(bg="#1e1f22", panel="#2b2d31", fg="#e3e3e3", muted="#9a9ca3", blocked="#6f7178",
               party="#24324a", border="#43454b", select="#3d5a80", button="#383a40",
               hover="#45474e", heading="#313338"),
}


def load_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f)
    except OSError:
        pass


def run_gui(initial=None):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, simpledialog

    if sys.platform == "win32":
        try:   # sharp text on high-DPI screens; hide the console if we own it
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            k32 = ctypes.windll.kernel32
            if k32.GetConsoleProcessList((ctypes.c_uint * 2)(), 2) == 1:
                ctypes.windll.user32.ShowWindow(k32.GetConsoleWindow(), 0)
        except Exception:
            pass

    root = tk.Tk()
    root.title("%s %s" % (APP_NAME, VERSION))
    root.geometry("980x640")
    root.minsize(760, 480)
    state = {"entries": [], "checked": set(), "path": None, "mons": [], "prof": None}
    keep_balls = tk.BooleanVar(value=False)
    settings = load_settings()
    dark = tk.BooleanVar(value=bool(settings.get("dark", False)))
    style = ttk.Style(root)
    native_theme = style.theme_use()
    colors = dict(PALETTES[False])

    # --- top bar
    top = ttk.Frame(root, padding=(10, 10, 10, 4))
    top.pack(fill="x")
    ttk.Button(top, text="Open Save…", command=lambda: choose()).pack(side="left")
    rom_btn = ttk.Button(top, text="Load ROM…", command=lambda: choose_rom())
    file_lbl = ttk.Label(top, text="No save loaded", style="Muted.TLabel")
    file_lbl.pack(side="left", padx=10)
    ttk.Checkbutton(top, text="Dark mode", variable=dark,
                    command=lambda: (apply_theme(), settings.update(dark=dark.get()),
                                     save_settings(settings))).pack(side="right")
    rom_lbl = ttk.Label(top, text="", style="Muted.TLabel")
    rom_lbl.pack(side="right", padx=(0, 14))

    # --- list
    mid = ttk.Frame(root, padding=(10, 4))
    mid.pack(fill="both", expand=True)
    cols = ("sel", "where", "pokemon", "sex", "lv", "nature", "ability", "games", "fmt", "status")
    heads = ("", "Location", "Pokémon", "♂/♀", "Lv", "Nature", "Ability", "Can go to", "File", "Notes")
    widths = (34, 130, 160, 40, 40, 76, 110, 80, 46, 210)
    tree = ttk.Treeview(mid, columns=cols, show="headings", selectmode="browse")
    for c, h, w in zip(cols, heads, widths):
        tree.heading(c, text=h)
        tree.column(c, width=w, anchor="center" if c in ("sel", "sex", "lv", "fmt", "games") else "w",
                    stretch=c in ("status", "pokemon"))
    sb = ttk.Scrollbar(mid, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    # --- details + buttons
    bottom = ttk.Frame(root, padding=(10, 4, 10, 10))
    bottom.pack(fill="x")
    details = tk.Text(bottom, height=8, wrap="word", relief="solid", borderwidth=1,
                      font=("TkDefaultFont", 10))
    details.pack(fill="x")
    details.insert("1.0", "Open a save to see its Pokémon. Click a row's box to tick or untick it. "
                   "If a gender or level doesn't match the game, click it to change it.\n\n"
                   "Supported ROM hacks:\n" + "\n".join("  • " + p.name for p in PROFILES))
    details.configure(state="disabled")
    opts = ttk.Frame(bottom, padding=(0, 6, 0, 0))
    opts.pack(fill="x")
    ttk.Checkbutton(opts, text="Keep original Poké Balls (some Pokémon can then only go to newer-generation games)",
                    variable=keep_balls, command=lambda: replan()).pack(side="left")
    bar = ttk.Frame(bottom, padding=(0, 8, 0, 0))
    bar.pack(fill="x")
    ttk.Label(bar, text="Select:").pack(side="left")
    ttk.Button(bar, text="Party", command=lambda: select("party")).pack(side="left", padx=2)
    ttk.Button(bar, text="All", command=lambda: select("all")).pack(side="left", padx=2)
    ttk.Button(bar, text="None", command=lambda: select("none")).pack(side="left", padx=2)
    export_btn = ttk.Button(bar, text="Export Selected…", command=lambda: do_export())
    export_btn.pack(side="right")
    count_lbl = ttk.Label(bar, text="")
    count_lbl.pack(side="right", padx=10)

    def apply_theme():
        """Switch between the system look and the dark skin."""
        on = dark.get()
        colors.clear()
        colors.update(PALETTES[on])
        c = colors
        if on:
            style.theme_use("clam")
            style.configure(".", background=c["bg"], foreground=c["fg"], fieldbackground=c["panel"],
                            bordercolor=c["border"], lightcolor=c["border"], darkcolor=c["border"],
                            troughcolor=c["bg"], focuscolor=c["select"], selectbackground=c["select"],
                            selectforeground="#ffffff", insertcolor=c["fg"])
            style.configure("TButton", background=c["button"], foreground=c["fg"], padding=(8, 3))
            style.map("TButton", background=[("disabled", c["bg"]), ("active", c["hover"])],
                      foreground=[("disabled", c["blocked"])])
            style.configure("TCheckbutton", background=c["bg"], foreground=c["fg"],
                            indicatorbackground=c["panel"], indicatorforeground=c["fg"])
            style.map("TCheckbutton", background=[("active", c["bg"])],
                      indicatorbackground=[("selected", c["select"]), ("active", c["hover"])])
            style.configure("Treeview", background=c["panel"], fieldbackground=c["panel"],
                            foreground=c["fg"], bordercolor=c["border"])
            style.map("Treeview", background=[("selected", c["select"])],
                      foreground=[("selected", "#ffffff")])
            style.configure("Treeview.Heading", background=c["heading"], foreground=c["fg"],
                            relief="flat")
            style.map("Treeview.Heading", background=[("active", c["hover"])])
            style.configure("Vertical.TScrollbar", background=c["button"], troughcolor=c["bg"],
                            arrowcolor=c["fg"], bordercolor=c["bg"])
            style.map("Vertical.TScrollbar", background=[("active", c["hover"])])
            root.configure(bg=c["bg"])
        else:
            style.theme_use(native_theme)
            root.configure(bg=style.lookup("TFrame", "background") or "SystemButtonFace")
        style.configure("Muted.TLabel", foreground=c["muted"])
        tree.tag_configure("blocked", foreground=c["blocked"])
        tree.tag_configure("party", background=c["party"])
        details.configure(bg=c["panel"], fg=c["fg"], insertbackground=c["fg"],
                          highlightbackground=c["border"], highlightcolor=c["border"],
                          relief="solid" if not on else "flat",
                          highlightthickness=0 if not on else 1)
        if sys.platform == "win32":     # dark title bar on Windows 10/11
            try:
                import ctypes
                hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
                value = ctypes.c_int(1 if on else 0)
                for attr in (20, 19):
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), 4)
                root.withdraw()
                root.deiconify()
            except Exception:
                pass

    def show_details(text):
        details.configure(state="normal")
        details.delete("1.0", "end")
        details.insert("1.0", text)
        details.configure(state="disabled")

    def refresh():
        for idx, e in enumerate(state["entries"]):
            tree.set(str(idx), "sel", "☑" if idx in state["checked"] else
                     ("☐" if e.exportable else "–"))
        n = len(state["checked"])
        count_lbl.configure(text="%d selected" % n)
        export_btn.state(["!disabled"] if n else ["disabled"])

    def make_entries():
        ov = state.setdefault("overrides", {})
        return [Entry(w, p, m, state["prof"], keep_balls.get(), *ov.get(i, (None, None)))
                for i, (w, p, m) in enumerate(state["mons"])]

    def render():
        entries = state["entries"]
        tree.delete(*tree.get_children())
        for idx, e in enumerate(entries):
            note = ("Can't export: " + e.blocker) if e.blocker else ("; ".join(e.notes))
            name = "%s (%s)" % (e.nickname, e.name) if getattr(e, "nicknamed", False) else e.name
            tags = ("blocked",) if not e.exportable else (("party",) if e.party else ())
            sex = getattr(e, "gender", getattr(e, "hack_gender", None))
            mark = lambda changed: "*" if changed else ""
            tree.insert("", "end", iid=str(idx), tags=tags, values=(
                "", e.where, name, {0: "♂", 1: "♀"}.get(sex, "") + mark(e.set_gender is not None)
                + ("?" if e.exportable and e.gender_unsure else ""),
                ("%s%s" % (e.level, mark(e.set_level))) if e.level else "", NATURES[e.m["pid"] % 25] if e.m["checksum_ok"] and not e.m["egg"] else "",
                ABILITIES[e.ability] if getattr(e, "ability", None) else "",
                "Gen %d+" % e.min_gen if e.format else "",
                ".pk%d" % e.format if e.format else "", note))
        refresh()

    def replan():
        if not state["mons"]:
            return
        sel = tree.selection()
        before = [e.exportable for e in state["entries"]]
        state["entries"] = make_entries()
        state["checked"] = {i for i, e in enumerate(state["entries"]) if e.exportable and
                            (i in state["checked"] or (e.party and not before[i]))}
        render()
        if sel:
            tree.selection_set(sel)
            show_details(state["entries"][int(sel[0])].summary())

    def choose_rom():
        prof = state["prof"]
        if not prof:
            return
        path = filedialog.askopenfilename(title="Choose the %s ROM (.gba)" % prof.short,
                                          filetypes=[("GBA ROM", "*.gba *.GBA"), ("All files", "*.*")])
        if not path:
            return
        try:
            prof.rom = RomTables(path, prof.needs_rom)
        except ExportError as err:
            messagebox.showerror(APP_NAME, str(err))
            return
        replan()
        rom_lbl.configure(text="ROM loaded ✓")
        show_details(prof.rom.summary + (" Pokémon are now identified from the ROM, and" if prof.needs_rom
                                         else "") + " Genders and levels now match the hack exactly.")

    def pick(profiles):
        """Ask which hack a save is from, when the save alone can't tell."""
        win = tk.Toplevel(root)
        if colors["bg"]:
            win.configure(bg=colors["bg"])
        win.title(APP_NAME)
        win.transient(root)
        win.grab_set()
        ttk.Label(win, text="This save could be from more than one ROM hack.\nWhich game is it from?",
                  padding=12).pack()
        choice = {"p": None}
        for prof in profiles:
            ttk.Button(win, text=prof.name, width=48,
                       command=lambda pr=prof: (choice.update(p=pr), win.destroy())).pack(padx=12, pady=3)
        ttk.Button(win, text="Cancel", command=win.destroy).pack(pady=(6, 12))
        root.wait_window(win)
        return choice["p"]

    def load(path):
        try:
            prof, trainer, mons = open_save(path, pick)
        except ExportError as err:
            if str(err) != "Cancelled.":
                messagebox.showerror(APP_NAME, str(err))
            return
        rom_btn.pack(side="left", padx=(6, 0), after=top.winfo_children()[0])
        rom_lbl.configure(text="ROM loaded ✓" if prof.rom else "No ROM")
        state.update(mons=mons, prof=prof, path=path, checked=set(), overrides={})
        state["entries"] = entries = make_entries()
        render()
        file_lbl.configure(text="%s   ·   %s   ·   Trainer %s   ·   %d Pokémon" % (
            os.path.basename(path), prof.name, trainer, len(entries)), style="TLabel")
        select("party")
        msg = ("Loaded %d Pokémon. Party Pokémon are ticked; tick any box Pokémon you also want.\n"
               "\"Can go to\" shows the oldest game generation each Pokémon can be moved into.\n"
               "If a gender (♂/♀) or level (Lv) doesn't match the game, click it to change it."
               % len(entries)) if entries else "No Pokémon found in this save."
        if prof.needs_rom and not prof.rom:
            msg += ("\n\n%s reuses Pokémon numbers, so the program needs the hack's ROM to identify "
                    "every Pokémon reliably. Click \"Load ROM…\" and pick your %s .gba file "
                    "(it's only read, never changed)." % (prof.short, prof.short))
        elif prof.check_genders and not prof.rom:
            msg += ("\n\n%s can change gender odds, and the save doesn't say which, so genders marked "
                    "with ? may not match the game. Compare them with each Pokémon's summary screen "
                    "and click ♂/♀ to change any that differ." % prof.short)
        elif not prof.rom:
            msg += ("\n\nTip: click \"Load ROM…\" and pick your %s .gba file. Hacks can change a "
                    "Pokémon's gender odds and level-up speed; with the ROM loaded, genders and levels "
                    "match what the game shows. (The ROM is only read, never changed.)" % prof.short)
        if prof.custom_abilities:
            msg += ("\n\nNote: %s changes some Pokémon's abilities. Exported Pokémon get the official "
                    "ability for the same slot, which may differ from what the game shows." % prof.short)
        show_details(msg)

    def choose():
        path = filedialog.askopenfilename(title="Choose a ROM hack save", filetypes=[
            ("Save files", "*.sav *.srm *.SAV *.SRM"), ("All files", "*.*")])
        if path:
            load(path)

    def select(which):
        es = state["entries"]
        state["checked"] = {i for i, e in enumerate(es) if e.exportable and
                            (which == "all" or (which == "party" and e.party))}
        refresh()

    def on_click(event):
        row = tree.identify_row(event.y)
        if not row:
            return
        idx = int(row)
        e = state["entries"][idx]
        show_details(e.summary())
        col = tree.identify_column(event.x)
        if col == "#1" and e.exportable:
            state["checked"] ^= {idx}
            refresh()
        elif col in ("#4", "#5") and e.exportable:
            root.after(1, lambda: (set_gender if col == "#4" else set_level)(idx))

    def set_gender(idx):
        """Flip a Pokemon's gender to match what the game shows."""
        e = state["entries"][idx]
        ratio = base_data(e.nat, e.form, e.format)[0] if e.format != 3 else UU[e.nat][0]
        if ratio in (0, 254, 255):
            show_details(e.summary() + "\n\nOfficial %s are always %s, so the gender can't be changed."
                         % (SPECIES[e.nat], {0: "male", 254: "female", 255: "genderless"}[ratio]))
            return
        g, lv = state["overrides"].get(idx, (None, None))
        state["overrides"][idx] = (1 - e.gender, lv)
        replan()

    def set_level(idx):
        """Set a Pokemon's level to match what the game shows."""
        e = state["entries"][idx]
        lv = simpledialog.askinteger(APP_NAME, "Level shown in the game for %s:" % e.name,
                                     initialvalue=e.level, minvalue=1, maxvalue=100, parent=root)
        if lv:
            g, _ = state["overrides"].get(idx, (None, None))
            state["overrides"][idx] = (g, lv)
            replan()

    def on_key(event):
        sel = tree.selection()
        if sel:
            idx = int(sel[0])
            if state["entries"][idx].exportable:
                state["checked"] ^= {idx}
                refresh()

    def on_select(event):
        sel = tree.selection()
        if sel:
            show_details(state["entries"][int(sel[0])].summary())

    tree.bind("<Button-1>", on_click)
    tree.bind("<space>", on_key)
    tree.bind("<<TreeviewSelect>>", on_select)

    def do_export():
        chosen = [state["entries"][i] for i in sorted(state["checked"])]
        if not chosen:
            return
        start = os.path.dirname(state["path"]) if state["path"] else None
        folder = filedialog.askdirectory(title="Choose where to save the files", initialdir=start)
        if not folder:
            return
        try:
            written = export(chosen, folder)
        except OSError as err:
            messagebox.showerror(APP_NAME, "Couldn't write the files:\n%s" % err)
            return
        if messagebox.askyesno(APP_NAME, "Exported %d Pokémon to:\n%s\n\nOpen the folder?"
                               % (len(written), folder)):
            open_folder(folder)

    apply_theme()
    refresh()
    if initial:
        root.after(100, lambda: load(initial))
    root.mainloop()


# =============================================================== text mode
def run_text(path, boxes, out, keep_balls=False, rom=None, hack=None, set_gender=(), set_level=()):
    if not path:
        path = input("Path to your save file: ").strip().strip('"').strip("'")

    def pick(profiles):
        if hack:
            for p in profiles:
                if hack.lower() in p.short.lower():
                    return p
        if not sys.stdin.isatty():
            print("This save could be from several hacks; using %s (choose with --hack)." % profiles[0].short)
            return profiles[0]
        print("This save could be from more than one ROM hack:")
        for i, p in enumerate(profiles, 1):
            print("  %d. %s" % (i, p.name))
        try:
            n = int(input("Which one? ").strip())
            return profiles[n - 1]
        except (ValueError, IndexError, EOFError):
            return None

    prof, trainer, mons = open_save(path, pick)
    if rom:
        prof.rom = RomTables(rom, prof.needs_rom)
        print(prof.rom.summary)
    elif prof.needs_rom:
        print("Tip: %s reuses Pokémon numbers. Add --rom \"your hack.gba\" so every Pokémon can\n"
              "be identified reliably.\n" % prof.short)
    elif prof.check_genders:
        print("Note: %s can change gender odds. Genders marked ? may not match the game; compare them\n"
              "with the summary screens and use --set-gender \"WHERE=F\" to change any that differ.\n"
              % prof.short)
    else:
        print("Tip: add --rom \"your hack.gba\" so genders and levels match the hack exactly.\n")
    genders = {}
    for item in set_gender:
        where, _, g = item.rpartition("=")
        genders[where.strip().lower()] = {"m": 0, "male": 0, "f": 1, "female": 1}[g.strip().lower()]
    levels = {}
    for item in set_level:
        where, _, lv = item.rpartition("=")
        levels[where.strip().lower()] = max(1, min(100, int(lv)))
    entries = [Entry(w, p, m, prof, keep_balls, genders.get(w.lower()), levels.get(w.lower()))
               for w, p, m in mons]
    print("%s %s\n%s - trainer %s\n" % (APP_NAME, VERSION, prof.name, trainer))
    if prof.custom_abilities:
        print("Note: %s changes some Pokémon's abilities. Exported Pokémon get the official\n"
              "ability for the same slot, which may differ from what the game shows.\n" % prof.short)
    chosen = []
    for e in entries:
        if not e.party and not boxes:
            continue
        print(e.summary().replace("\n", "\n    "))
        print()
        if e.exportable:
            chosen.append(e)
    if not boxes and any(not e.party for e in entries):
        print("(Box Pokémon not included - add --boxes to export them too.)")
    folder = out or os.path.splitext(path)[0] + "_export"
    written = export(chosen, folder)
    print("Done: %d file(s) written to %s" % (len(written), os.path.abspath(folder)))


def main():
    ap = argparse.ArgumentParser(description="Export Pokemon from ROM hack saves as .pk files.")
    ap.add_argument("save", nargs="?", help="save file (with --text; otherwise opens in the window)")
    ap.add_argument("--text", action="store_true", help="use text mode instead of the window")
    ap.add_argument("--boxes", action="store_true", help="text mode: also export PC boxes")
    ap.add_argument("-o", "--out", help="text mode: output folder")
    ap.add_argument("--rom", help="text mode: the hack's .gba file (for exact genders and levels; "
                                  "needed to identify Light Platinum Pokemon)")
    ap.add_argument("--hack", help="text mode: which hack, if the save could be from several "
                                   "(e.g. --hack gaia)")
    ap.add_argument("--set-gender", action="append", default=[], metavar='"WHERE=F"',
                    help='text mode: set a gender to match the game, e.g. --set-gender "Party 4=F"')
    ap.add_argument("--set-level", action="append", default=[], metavar='"WHERE=LV"',
                    help='text mode: set a level to match the game, e.g. --set-level "BOX1, slot 2=5"')
    ap.add_argument("--keep-balls", action="store_true",
                    help="text mode: keep original Poke Balls, even if that limits a Pokemon to newer-generation games")
    args = ap.parse_args()
    if not args.text:
        try:
            import tkinter  # noqa: F401
        except ImportError:
            print("(No window toolkit found - using text mode.)\n")
            args.text = True
    try:
        if args.text:
            run_text(args.save, args.boxes, args.out, args.keep_balls, args.rom, args.hack,
                     args.set_gender, args.set_level)
        else:
            run_gui(args.save)
    except ExportError as err:
        sys.exit(str(err))


if __name__ == "__main__":
    main()
