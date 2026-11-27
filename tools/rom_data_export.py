"""ROM data export - a developer tool for Pokemon Hack Porter (not part of the releases).

Reads a hack's ROM with the porter's own ROM reader and writes a small text file
(CSV) with each Pokemon's gender ratio and growth rate as the hack stores them.
Only numbers are written - nothing from the game itself. Those numbers can then be
built into the porter, so genders and levels are right without loading the ROM.

How to use (needs Python 3.8+):
  * Double-click this file and pick one or more .gba files, or
  * run:  python tools/rom_data_export.py "Lazarus.gba" "Unbound.gba" ...
The .csv files are written next to each ROM, named after it.

It needs pokemon_hack_porter.py from the same download (the repository root, or
the same folder as this file)."""
import binascii
import importlib.util
import os
import sys


def load_porter():
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(here, "..", "pokemon_hack_porter.py"),
                 os.path.join(here, "pokemon_hack_porter.py")):
        if os.path.exists(path):
            spec = importlib.util.spec_from_file_location("porter", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise SystemExit("Couldn't find pokemon_hack_porter.py. Put this file next to it, "
                     "or run it from the repository's tools folder.")


def export(php, rom_path):
    """Write <rom name>.csv next to the ROM and return (csv path, summary)."""
    with open(rom_path, "rb") as f:
        rom = f.read()
    try:                                           # hacks with a name list (Light Platinum)
        tables = php.RomTables(rom_path, need_names=True)
    except php.ExportError:
        tables = php.RomTables(rom_path, need_names=False)
    if not tables.stats:
        raise php.ExportError("No species data table found.\nDetails: " + "; ".join(php.STATS_DIAG[:8]))
    def text(raw):                                 # header text, printable characters only
        return "".join(chr(c) if 32 <= c < 127 else "?" for c in raw).strip("? ")
    title, code = text(rom[0xA0:0xAC]), text(rom[0xAC:0xB0])
    out = os.path.splitext(rom_path)[0] + "_romdata.csv"
    names = getattr(tables, "species_names", {}) or {}
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("# Pokemon Hack Porter ROM data export (porter %s)\n" % php.VERSION)
        f.write("# file: %s\n" % os.path.basename(rom_path))
        f.write("# size: %d  crc32: %08X  header: %s %s\n"
                % (len(rom), binascii.crc32(rom) & 0xFFFFFFFF, title, code))
        f.write("# search: %s\n" % "; ".join(php.STATS_DIAG[-3:]))
        f.write("id,name_in_rom,gender_ratio,growth_rate\n")
        for i in sorted(tables.stats):
            g, r = tables.stats[i]
            f.write("%d,%s,%d,%d\n" % (i, names.get(i, "").replace(",", " "), g, r))
    return out, "%s: %d Pokémon" % (os.path.basename(out), len(tables.stats))


def main():
    php = load_porter()
    paths = sys.argv[1:]
    gui = not paths
    if gui:
        import tkinter as tk
        from tkinter import filedialog, messagebox
        root = tk.Tk()
        root.withdraw()
        paths = filedialog.askopenfilenames(title="Pick hack ROMs to export data from",
                                            filetypes=[("GBA ROM", "*.gba"), ("All files", "*.*")])
        if not paths:
            return
    done, failed = [], []
    for p in paths:
        try:
            done.append(export(php, p)[1])
        except Exception as e:                    # report every ROM, keep going
            failed.append("%s: %s" % (os.path.basename(p), e))
    report = ""
    if done:
        report += "Saved next to each ROM:\n" + "\n".join(done)
    if failed:
        report += ("\n\n" if report else "") + "Couldn't read:\n" + "\n".join(failed)
    if gui:
        (messagebox.showinfo if not failed else messagebox.showwarning)("ROM data export", report)
    else:
        print(report)
        sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
