#!/usr/bin/env python3
"""Pin the Linux release binaries in .chezmoidata/linux.json.

    python3 lib/linux_releases.py pin [name ...]   # newest release >= 7 days old
    python3 lib/linux_releases.py pin --keep [name ...]  # re-verify the current tags
    python3 lib/linux_releases.py list

For each release it records the tag, the version, every architecture's sha256 and,
for archives, the member path of each binary. .chezmoiexternal.toml.tmpl turns
those into pinned, checksummed externals. The seven-day minimum mirrors the npm/uv
release cooldown (~/.npmrc min-release-age). Needs `gh` (authenticated) for the API.
"""
import datetime as dt
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, ".chezmoidata", "linux.json")
COOLDOWN = dt.timedelta(days=7)
ARCHIVE_SUFFIXES = (".tar.gz", ".tgz", ".zip")


def gh_json(path):
    out = subprocess.run(["gh", "api", path], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def pick_release(repo, keep_tag=None):
    if keep_tag:
        return gh_json(f"repos/{repo}/releases/tags/{keep_tag}")
    cutoff = dt.datetime.now(dt.timezone.utc) - COOLDOWN
    for rel in gh_json(f"repos/{repo}/releases?per_page=40"):
        if rel["draft"] or rel["prerelease"]:
            continue
        published = dt.datetime.fromisoformat(rel["published_at"].replace("Z", "+00:00"))
        if published <= cutoff:
            return rel
    raise SystemExit(f"{repo}: no release older than {COOLDOWN.days} days")


def download(url):
    req = urllib.request.Request(url, headers={"User-Agent": "dotfiles-linux-releases"})
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def find_members(blob, asset, bins):
    """Map each binary name to its unique regular-file member path in the archive."""
    if asset.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            names = [n for n in zf.namelist() if not n.endswith("/")]
    else:
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
            names = [m.name for m in tf.getmembers() if m.isfile()]
    found = {}
    for b in bins:
        hits = [n for n in names if os.path.basename(n) == b]
        if len(hits) != 1:
            raise SystemExit(f"{asset}: expected one member named {b}, found {hits or 'none'}")
        found[b] = hits[0]
    return found


def pin_one(name, entry, keep):
    rel = pick_release(entry["repo"], entry.get("tag") if keep else None)
    tag = rel["tag_name"]
    version = tag[1:] if tag.startswith("v") else tag
    assets = {a["name"] for a in rel["assets"]}
    bins = [name] + entry.get("extra_bins", [])
    sha256, members = {}, {}
    for arch, token in entry["arch"].items():
        asset = entry["asset"].replace("{version}", version).replace("{arch}", token)
        if asset not in assets:
            raise SystemExit(f"{name} {tag}: no asset {asset} (have: {', '.join(sorted(assets))})")
        url = f"https://github.com/{entry['repo']}/releases/download/{tag}/{asset}"
        blob = download(url)
        sha256[arch] = hashlib.sha256(blob).hexdigest()
        if asset.endswith(ARCHIVE_SUFFIXES):
            members[arch] = find_members(blob, asset, bins)
        elif len(bins) > 1:
            raise SystemExit(f"{name}: extra_bins needs an archive asset")
    entry.update(tag=tag, version=version, published=rel["published_at"][:10], sha256=sha256)
    if members:
        entry["members"] = members
    else:
        entry.pop("members", None)
    print(f"{name:10} {tag:14} published {entry['published']}")


def main(argv):
    if not argv or argv[0] not in ("pin", "list"):
        raise SystemExit(__doc__)
    with open(MANIFEST) as f:
        data = json.load(f)
    releases = data["linux"]["releases"]
    if argv[0] == "list":
        for name, e in sorted(releases.items()):
            print(f"{name:10} {e.get('tag', '(unpinned)'):14} {e.get('published', '')}")
        return
    args = argv[1:]
    keep = "--keep" in args
    names = [a for a in args if a != "--keep"] or sorted(releases)
    for name in names:
        if name not in releases:
            raise SystemExit(f"unknown release {name}")
        pin_one(name, releases[name], keep)
    with open(MANIFEST, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main(sys.argv[1:])
