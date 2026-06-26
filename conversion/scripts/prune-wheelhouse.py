#!/usr/bin/env python3
import argparse
import os
import re
from collections import defaultdict

WHEEL_RE = re.compile(
    r"^(?P<name>.+)-(?P<ver>[^-]+)-(?P<py>[^-]+)-(?P<abi>[^-]+)-(?P<plat>[^-]+)\.whl$"
)


def normalize_name(name: str) -> str:
    return name.replace("-", "_").lower()


def score(meta: dict, target_py: str) -> int:
    s = 0
    py = meta["py"].lower()
    abi = meta["abi"].lower()
    plat = meta["plat"].lower()

    if py == target_py:
        s += 100
    elif py.startswith("py3"):
        s += 60

    if abi == target_py:
        s += 40
    elif abi == "abi3":
        s += 20
    elif abi == "none":
        s += 5

    if "manylinux" in plat:
        s += 20
    if "x86_64" in plat:
        s += 10
    if plat == "any":
        s += 2
    return s


def main() -> int:
    parser = argparse.ArgumentParser(description="Prune redundant wheel files by target runtime.")
    parser.add_argument("--wheel-dir", default="wheels", help="Wheel directory")
    parser.add_argument("--target-py", default="cp311", help="Target python tag, e.g. cp311")
    parser.add_argument("--apply", action="store_true", help="Actually delete redundant files")
    args = parser.parse_args()

    if not os.path.isdir(args.wheel_dir):
        print(f"wheel dir not found: {args.wheel_dir}")
        return 1

    files = [f for f in os.listdir(args.wheel_dir) if f.endswith(".whl")]
    groups = defaultdict(list)

    for f in files:
        m = WHEEL_RE.match(f)
        if not m:
            continue
        meta = m.groupdict()
        meta["file"] = f
        key = (normalize_name(meta["name"]), meta["ver"])
        groups[key].append(meta)

    remove = []
    keep = []

    for _, metas in sorted(groups.items()):
        if len(metas) == 1:
            keep.append(metas[0]["file"])
            continue

        metas_sorted = sorted(metas, key=lambda m: score(m, args.target_py), reverse=True)
        winner = metas_sorted[0]
        keep.append(winner["file"])
        for m in metas_sorted[1:]:
            remove.append((winner["file"], m["file"]))

    if not remove:
        print("No redundant wheel variants found.")
        return 0

    print("Redundant wheel variants:")
    for winner, loser in remove:
        print(f"  keep: {winner}")
        print(f"  drop: {loser}")

    if args.apply:
        for _, loser in remove:
            path = os.path.join(args.wheel_dir, loser)
            if os.path.exists(path):
                os.remove(path)
                print(f"deleted: {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
