"""What each Pokemon in tests/saves looks like IN THE GAME, copied from in-game
summary screenshots taken by the project owner (Nick) on 2026-11-26.
This is the ground truth the program is checked against.

Fields: where (as the program labels it), species, level, gender (M/F/-),
nature, moves (in order), met level, exp (None if not on screen).
"hack" notes list things the hack shows that official games can't have.
Also seen on screen but not checked here: OT names/IDs (all matched), balls,
held items (dropped on purpose) and stats (they matched the IVs the program reads;
Gaia and Lazarus show IV letter grades, which also matched)."""

EXPECTED = {
    "imperium.sav": {  # Pokemon Emerald Imperium v1.3.1, trainer A, ID 41989
        "Party 1":       ("Piplup", 10, "M", "Rash", ["Pound", "Growl", "Bubble", "Aqua Jet"], 5, 579),
        "Box1, slot 1":  ("Blipbug", 5, "M", "Bold", ["Struggle Bug"], 5, None),
        "Box1, slot 2":  ("Meowth (Alolan)", 4, "F", "Rash", ["Scratch", "Growl"], 4, 64),
    },
    "odyssey.sav": {  # Pokemon Odyssey v4.1, trainer Nyx, ID 58317
        "Party 1":       ("Plusle", 7, "F", "Brave", ["Thunder Shock", "Tackle", "Helping Hand", "Thunder Wave"], 5, 427),
        "Party 2":       ("Minun", 7, "M", "Hasty", ["Thunder Shock", "Tackle", "Helping Hand", "Charge"], 5, 427),
        "Party 3":       ("Zigzagoon", 3, "M", "Hardy", ["Tackle", "Growl"], 3, 62),
        "BOX1, slot 1":  ("Geodude", 4, "M", "Bold", ["Tackle", "Defense Curl"], 4, 96),
        "BOX1, slot 2":  ("Poochyena", 3, "M", "Quirky", ["Tackle", "Howl"], 3, 51),
    },
    "light_platinum.sav": {  # Pokemon Light Platinum, trainer AAA, ID 35622
        "Party 1":       ("Bulbasaur", 14, "F", "Bold", ["Tackle", "Growl", "Leech Seed", "Vine Whip"], 5, 1717),
        "BOX1, slot 1":  ("Starly", 2, "M", "Adamant", ["Tackle", "Growl"], 2, 31),
        "BOX1, slot 2":  ("Bidoof", 5, "M", "Gentle", ["Tackle", "Growl"], 3, 109),
    },
    "unbound.sav": {  # Pokemon Unbound v2.1.1.1, trainer Aaaa, ID 01411
        "Party 1":       ("Beldum", 11, "-", "Naughty", ["Tackle", "Flash"], 10, 969),
        "Box 1, slot 1": ("Vanillite", 9, "F", "Quirky", ["Astonish", "Harden", "Taunt", "Mist"], 9, 962),
        "Box 1, slot 2": ("Snorunt", 9, "M", "Quirky", ["Astonish", "Leer"], 9, 729),
    },
    "gaia.sav": {  # Pokemon Gaia v3.2, trainer Terra, ID 55685
        "Party 1":       ("Chimchar", 6, "M", "Gentle", ["Scratch", "Leer"], 5, 197),
        "Box1, slot 1":  ("Bidoof", 3, "M", "Modest", ["Tackle"], 3, 27),
        "Box1, slot 2":  ("Budew", 2, "M", "Lonely", ["Absorb"], 2, 9),
    },
    "lazarus.sav": {  # Pokemon Lazarus v2.0, trainer N, ID 13469
        "Party 1":       ("Murkrow", 13, "F", "Adamant", ["Peck", "Astonish", "Pursuit", "Haze"], 6, None),
        "Party 2":       ("Shroomish", 13, "M", "Sassy", ["Mega Drain", "Tackle", "Stun Spore", "Leech Seed"], 3, 1370),
        "Party 3":       ("Mareep", 13, "F", "Modest", ["Tackle", "Cotton Spore", "Thunder Wave", "Thunder Shock"], 4, 1365),
        "Party 4":       ("Fennekin", 14, "F", "Quiet", ["Scratch", "Flame Charge", "Ember", "Howl"], 5, 1920),
        "Box1, slot 1":  ("Vulpix", 1, "F", "Sassy", ["Ember"], 1, 1),
        "Box1, slot 2":  ("Eevee", 1, "M", "Lonely", ["Helping Hand", "Growl", "Tackle", "Tail Whip"], 1, 1),
    },
}

# Things the hacks show that official files can't hold (expected, not bugs).
HACK_ONLY = {
    "odyssey.sav": "Poochyena shows Fur Coat and is Ice/Dark; Plusle/Minun have buffed stats.",
    "light_platinum.sav": "Bidoof shows Pickup. Bidoof levels up faster than official (Lv 5 at 109 EXP).",
    "unbound.sav": "Beldum also knows Metal Bash (Unbound-only move, ID 499) and levels up faster.",
    "gaia.sav": "Bidoof shows Run Away (its Hidden Ability slot in Gaia).",
    "lazarus.sav": "Fennekin is female: Lazarus changed Fennekin's gender odds. Vulpix/Eevee are in Cherish Balls.",
}

# Without the hack's ROM these can't match (the save alone doesn't say). With the ROM loaded they must.
NEEDS_ROM = {("light_platinum.sav", "BOX1, slot 2", "level"), ("lazarus.sav", "Party 4", "gender")}
