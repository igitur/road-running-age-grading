#!/bin/sh
# apply-xll-patches.sh — recreate the mingw-portable xll library.
#
# The xll framework is MSVC-only upstream: five of its headers use MSVC
# preprocessor extensions and one file relies on MSVC's pragma-based exports.
# patches/xll-mingw-portability.patch makes it compile with mingw-w64 and export
# its symbols from a .def file. See docs/framework-patches.md for what each hunk
# fixes and the exact error it removes.
#
#   ./tools/apply-xll-patches.sh                 # into $XLL_DIR (default ~/code/xll)
#   XLL_DIR=/opt/xll ./tools/apply-xll-patches.sh
#
# Safe to re-run: it detects an already-patched tree and does nothing.

set -eu

here=$(cd "$(dirname "$0")" && pwd)
patch_file="$here/../patches/xll-mingw-portability.patch"
XLL_DIR="${XLL_DIR:-$HOME/code/xll}"
UPSTREAM="https://github.com/xlladdins/xll"

[ -f "$patch_file" ] || { echo "missing $patch_file" >&2; exit 1; }

if [ ! -d "$XLL_DIR/xll" ]; then
    echo "cloning $UPSTREAM into $XLL_DIR"
    git clone --depth 1 "$UPSTREAM" "$XLL_DIR"
fi

cd "$XLL_DIR"

if git apply --reverse --check "$patch_file" >/dev/null 2>&1; then
    echo "already patched: $XLL_DIR"
    exit 0
fi

if ! git apply --check "$patch_file" >/dev/null 2>&1; then
    echo "cannot apply $patch_file to $XLL_DIR" >&2
    echo "upstream may have changed; regenerate the patch against the new HEAD" >&2
    git apply --check --verbose "$patch_file" 2>&1 | tail -5 >&2 || true
    exit 1
fi

git apply "$patch_file"
echo "patched $XLL_DIR"
git --no-pager diff --stat
