#!/usr/bin/env python3
import os
import platform
import shutil
from pathlib import Path
import curses
import stat
import argparse

# ------------------------
# CONFIGURATION
# ------------------------
HOSTNAME = os.uname().nodename
SYSTEM_ARCH = platform.machine()  # x86_64, aarch64, riscv64, etc.
MAKECONF_DIR = Path(f"/etc/portage/make.conf/{HOSTNAME}")
TARGET = Path("/etc/portage/make.conf")
OLD_DIR = MAKECONF_DIR / "old"

# Ensure directories exist
MAKECONF_DIR.mkdir(parents=True, exist_ok=True)
OLD_DIR.mkdir(exist_ok=True)

# ------------------------
# Initialize prod/dev/custom/test if missing (vanilla)
# ------------------------
def init_makeconfs():
    for label in ["prod", "dev", "custom", "test"]:
        f = MAKECONF_DIR / f"{label}-{SYSTEM_ARCH}-make.conf"
        if not f.exists():
            f.write_text(f"# {label} make.conf for {HOSTNAME} [{SYSTEM_ARCH}]\n")
        if label == "prod":
            # prod is read-only for safety
            f.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)  # 444

# ------------------------
# Backup current make.conf
# ------------------------
def backup_current():
    if TARGET.exists() and TARGET.is_file():
        n = 1
        while (OLD_DIR / f"make.conf.backup{n}").exists():
            n += 1
        shutil.copy2(TARGET, OLD_DIR / f"make.conf.backup{n}")

# ------------------------
# List make.conf files filtered by arch
# ------------------------
def list_makeconfs():
    files = [f for f in MAKECONF_DIR.iterdir() if f.is_file()]
    return sorted([f for f in files if SYSTEM_ARCH.lower() in f.name.lower()])

# ------------------------
# Safe symlink set
# ------------------------
def symlink_safe(selected_file: Path):
    if SYSTEM_ARCH.lower() not in selected_file.name.lower():
        print(f"ERROR: {selected_file.name} does not match host arch {SYSTEM_ARCH}")
        return False
    backup_current()
    if TARGET.exists() or TARGET.is_symlink():
        TARGET.unlink()
    TARGET.symlink_to(selected_file)
    print(f"Symlinked {selected_file.name} -> {TARGET}")
    return True

# ------------------------
# Copy configs from another host (same arch)
# ------------------------
def copy_from_host(src_host: str):
    src_dir = Path(f"/etc/portage/make.conf/{src_host}")
    if not src_dir.exists():
        print(f"Source host folder {src_dir} not found")
        return
    for f in src_dir.iterdir():
        if SYSTEM_ARCH.lower() in f.name.lower():
            shutil.copy2(f, MAKECONF_DIR / f.name)
            print(f"Copied {f.name} from {src_host} -> {HOSTNAME}")

# ------------------------
# TUI selection
# ------------------------
def tui(stdscr):
    curses.curs_set(0)
    stdscr.clear()
    files = list_makeconfs()
    if not files:
        stdscr.addstr(0, 0, f"No make.conf matching {SYSTEM_ARCH} found in {MAKECONF_DIR}")
        stdscr.addstr(2, 0, "Edit manually or copy from another host.")
        stdscr.refresh()
        stdscr.getch()
        return

    idx = 0
    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, f"Select make.conf for {HOSTNAME} [{SYSTEM_ARCH}]: (arrows + Enter, q=quit)")
        for i, f in enumerate(files):
            marker = "*" if i == idx else " "
            stdscr.addstr(i + 2, 2, f"{marker} {f.name}")
        stdscr.refresh()

        key = stdscr.getch()
        if key in [curses.KEY_UP, ord('k')]:
            idx = (idx - 1) % len(files)
        elif key in [curses.KEY_DOWN, ord('j')]:
            idx = (idx + 1) % len(files)
        elif key in [curses.KEY_ENTER, ord('\n')]:
            symlink_safe(files[idx])
            stdscr.addstr(len(files)+3, 0, f"Hot switch complete. Backup saved in ./old/")
            stdscr.refresh()
            stdscr.getch()
            break
        elif key in [ord('q')]:
            break

# ------------------------
# Purge old backups
# ------------------------
def purge_old_backups():
    backups = sorted(OLD_DIR.glob("make.conf.backup*"))
    if not backups:
        print("No old backups to purge.")
        return
    for b in backups:
        print(f"Removing {b}")
        b.unlink()
    print("All old backups removed.")

# ------------------------
# Revert to most recent backup
# ------------------------
def revert_last_backup():
    backups = sorted(OLD_DIR.glob("make.conf.backup*"), reverse=True)
    if not backups:
        print("No backups found to revert to.")
        return
    latest = backups[0]
    if TARGET.exists() or TARGET.is_symlink():
        TARGET.unlink()
    TARGET.symlink_to(latest)
    print(f"Reverted {TARGET} -> {latest}")

# ------------------------
# CLI commands
# ------------------------
def main():
    parser = argparse.ArgumentParser(description="Gentoo make.conf life guard")
    parser.add_argument(
        "command",
        choices=["list", "set", "show", "copy-from-host", "tui", "purge-old", "revert"],
        help="Command to run"
    )
    parser.add_argument("file_or_host", nargs="?", help="File name or host for copy")
    args = parser.parse_args()

    init_makeconfs()

    if args.command == "list":
        for f in list_makeconfs():
            print(f.name)
    elif args.command == "set":
        if not args.file_or_host:
            print("Please specify make.conf file to set")
            return
        f = MAKECONF_DIR / args.file_or_host
        if not f.exists():
            print(f"{f} not found")
            return
        symlink_safe(f)
    elif args.command == "show":
        if TARGET.exists() or TARGET.is_symlink():
            print(TARGET.resolve())
        else:
            print("No active make.conf")
    elif args.command == "copy-from-host":
        if not args.file_or_host:
            print("Please specify source host")
            return
        copy_from_host(args.file_or_host)
    elif args.command == "tui":
        curses.wrapper(tui)
    elif args.command == "purge-old":
        purge_old_backups()
    elif args.command == "revert":
        revert_last_backup()

if __name__ == "__main__":
    main()
