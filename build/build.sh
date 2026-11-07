#!/usr/bin/env bash
# Build Companion Mono and Companion Mono Unison from the pinned Iosevka release.
#
#   bash build/build.sh         all hinted styles -> fonts/, then finalize, verify, and
#                               check weights
#   bash build/build.sh draft   unhinted TTFs only -> .cache/draft/, then check weights
#   bash build/build.sh line    Companion Mono Line, single-stroke SVG fonts for pen
#                               plotters -> fonts/svg/
#
# build/iosevka.patch redraws Iosevka's keyboard symbols and thick arrows. Iosevka builds
# and hints Companion Mono. It builds Unison unhinted; build/scale-unison.py scales it, and
# this script then hints it as Iosevka would, with Iosevka's glyph-to-script controls. The
# Iosevka checkout and its build cache live in .cache/iosevka, so later builds are
# incremental. JOBS sets concurrent build jobs (default 2; each can use more than 1 GB).
set -euo pipefail

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
iosevka="$root/.cache/iosevka"
tag=v34.9.0
commit=2487637bb71f41b2a66134afd9faa6c316e5a438
plans=(CompanionMono CompanionMonoItalic CompanionMonoSemiExtended CompanionMonoSemiExtendedItalic)
unison=(CompanionMonoUnison CompanionMonoUnisonItalic)

for dependency in git node npm uv; do
  command -v "$dependency" >/dev/null || { printf 'Missing dependency: %s\n' "$dependency" >&2; exit 1; }
done

if [[ ! -d "$iosevka" ]]; then
  git -c advice.detachedHead=false clone --quiet --depth 1 --branch "$tag" \
    https://github.com/be5invis/Iosevka.git "$iosevka"
fi
[[ "$(git -C "$iosevka" rev-parse HEAD)" == "$commit" ]] || {
  printf '%s is not at the pinned commit %s\n' "$iosevka" "$commit" >&2
  exit 1
}
[[ -d "$iosevka/node_modules" ]] || (cd "$iosevka" && npm ci --no-audit --no-fund)

# The checkout keeps a copy of the patch it has applied, so an unchanged patch leaves the
# sources, and so the build cache, untouched. A changed patch is applied in place of the old
# one, unless the sources already have its changes, or have changes that neither patch has.
patch="$root/build/iosevka.patch"
applied="$iosevka/companion-mono.patch"
sources_match() { git -C "$iosevka" diff | cmp -s - "$1"; }
if ! cmp -s "$patch" "$applied"; then
  if ! sources_match "$patch"; then
    git -C "$iosevka" diff --quiet || sources_match "$applied" || {
      printf '%s has changes that build/iosevka.patch lacks. Save them into the patch, or\n' \
        "$iosevka" >&2
      printf 'discard them with: git -C %s checkout -- .\n' "$iosevka" >&2
      exit 1
    }
    git -C "$iosevka" checkout --quiet -- .
    git -C "$iosevka" apply "$patch"
  fi
  cp "$patch" "$applied"
fi

# Line traces the stroke centerlines of each glyph's construction at a hairline weight and
# writes them as SVG fonts at Unison's size. It reads the build plans directly.
if [[ "${1:-}" == line ]]; then
  traced="$root/.cache/line"
  mkdir -p "$traced" "$root/fonts/svg"
  for slope in "CompanionMono 0 upright" "CompanionMonoItalic 11 italic"; do
    read -r plan angle name <<<"$slope"
    node "$root/build/line/extract.mjs" "$iosevka" "$root/build/private-build-plans.toml" \
      "$plan" 100 "$angle" "$traced/$name.json"
  done
  uv run --quiet "$root/build/line/write_svg.py" "$traced/upright.json" \
    "Companion Mono Line" "$root/fonts/svg/CompanionMonoLine.svg"
  uv run --quiet "$root/build/line/write_svg.py" "$traced/italic.json" \
    "Companion Mono Line Italic" "$root/fonts/svg/CompanionMonoLineItalic.svg"
  exit
fi

# Verda's journal remembers each plan's old style list and fails on styles a changed plan
# no longer has, so a changed plan starts from a clean journal and dist.
if ! cmp -s "$root/build/private-build-plans.toml" "$iosevka/private-build-plans.toml"; then
  rm -rf "$iosevka/.build/.verda-build-journal" "$iosevka/dist"
  cp "$root/build/private-build-plans.toml" "$iosevka/private-build-plans.toml"
fi
export TTFAUTOHINT_PATH="$root/build/ttfautohint"
# Iosevka, ttfautohint, and fontTools stamp fonts with the last commit's time instead of the
# build time, so builds of the same commit and toolchain are identical.
SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-$(git -C "$root" log -1 --format=%ct)}
export SOURCE_DATE_EPOCH
cd "$iosevka"

# collect FORMAT_DIR DEST [hint]: replace DEST with each style under its final
# CompanionMono-<style> or CompanionMonoUnison-<style> name, so no style from an older plan
# lingers there. Unison's unhinted styles are scaled first, then hinted if asked.
collect() {
  local scaled="$root/.cache/unison" plan ttf base
  rm -rf "$2" "$scaled"
  mkdir -p "$2" "$scaled"
  for plan in "${plans[@]}"; do
    for ttf in "dist/$plan/$1/"*.ttf; do
      cp "$ttf" "$2/CompanionMono-${ttf##*/$plan-}"
    done
  done
  for plan in "${unison[@]}"; do
    uv run --quiet "$root/build/scale-unison.py" "$scaled" "dist/$plan/TTF-Unhinted/"*.ttf
    for ttf in "$scaled/$plan-"*.ttf; do
      base=${ttf##*/}
      if [[ "${3:-}" == hint ]]; then
        "$TTFAUTOHINT_PATH" -m ".build/TTF/$plan/${base%.ttf}.ttfa.txt" "$ttf" \
          "$2/CompanionMonoUnison-${base#"$plan"-}"
      else
        cp "$ttf" "$2/CompanionMonoUnison-${base#"$plan"-}"
      fi
    done
  done
}

if [[ "${1:-}" == draft ]]; then
  npm run build -- "${plans[@]/#/ttf-unhinted::}" "${unison[@]/#/ttf-unhinted::}" \
    "--jCmd=${JOBS:-2}"
  collect TTF-Unhinted "$root/.cache/draft"
  printf 'Draft fonts: %s\n' "$root/.cache/draft"
  uv run --quiet "$root/build/check-weights.py" "$root/.cache/draft"
  exit
fi

npm run build -- "${plans[@]/#/ttf::}" "${unison[@]/#/ttf-unhinted::}" "--jCmd=${JOBS:-2}"
collect TTF "$root/fonts/ttf" hint

cd "$root"
uv run --quiet build/finalize.py
uv run --quiet build/verify-fonts.py
uv run --quiet build/check-weights.py
printf 'Installed fonts into %s\n' "$root/fonts"
