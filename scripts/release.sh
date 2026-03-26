#!/usr/bin/env bash
set -euo pipefail

# Release script for Dexter
# Usage: bash scripts/release.sh [version]
# If no version is provided, defaults to today's date as YYYY.M.D

VERSION="${1:-$(date +%Y.%-m.%-d)}"
TAG="v${VERSION}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "$REPO_ROOT"

# Ensure gh CLI is available
if ! command -v gh &>/dev/null; then
  echo "Error: gh CLI is required. Install it: https://cli.github.com"
  exit 1
fi

# Ensure working tree is clean
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Error: working tree is dirty. Commit or stash changes first."
  exit 1
fi

# Find the previous tag (most recent), or use root commit if none exist
PREV_TAG=$(git describe --tags --abbrev=0 2>/dev/null || true)
if [[ -z "$PREV_TAG" ]]; then
  RANGE="HEAD"
else
  RANGE="${PREV_TAG}..HEAD"
fi

echo "Releasing ${TAG}"
echo "Commits: ${RANGE}"
echo ""

# Collect commits and categorize into Changes and Fixes
CHANGES=""
FIXES=""

while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  # Extract subject (everything after the short hash + space)
  subject="${line#* }"
  if echo "$subject" | grep -qi "^fix"; then
    FIXES="${FIXES}- ${subject}\n"
  else
    CHANGES="${CHANGES}- ${subject}\n"
  fi
done < <(git log --oneline --no-merges "$RANGE" | grep -v "^.*Bump version$")

# Build release body
BODY=""
if [[ -n "$CHANGES" ]]; then
  BODY+="### Changes\n\n${CHANGES}\n"
fi
if [[ -n "$FIXES" ]]; then
  BODY+="### Fixes\n\n${FIXES}\n"
fi

if [[ -z "$BODY" ]]; then
  echo "Error: no commits found for release notes."
  exit 1
fi

# Preview
echo "--- Release notes ---"
echo -e "$BODY"
echo "---------------------"
echo ""

# Prompt for confirmation
read -rp "Create release ${TAG}? [y/N] " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
  echo "Aborted."
  exit 0
fi

# Bump version in pyproject.toml and dexter_flask/__init__.py
CURRENT_VERSION=$(python3 -c "import tomli; from pathlib import Path; data=tomli.loads(Path('pyproject.toml').read_text('utf-8')); print(data['project']['version'])")
if [[ "$CURRENT_VERSION" != "$VERSION" ]]; then
  python3 - <<PY
import re
from pathlib import Path

version = "${VERSION}"

pyproject = Path("pyproject.toml")
txt = pyproject.read_text(encoding="utf-8")
txt2 = re.sub(r'^version = \"[^\"]+\"$', f'version = \"{version}\"', txt, flags=re.M)
if txt2 == txt:
    raise SystemExit("Failed to update version in pyproject.toml")
pyproject.write_text(txt2, encoding="utf-8")

init_py = Path("dexter_flask/__init__.py")
txt = init_py.read_text(encoding="utf-8")
txt2 = re.sub(r'^__version__ = \"[^\"]+\"$', f'__version__ = \"{version}\"', txt, flags=re.M)
if txt2 == txt:
    raise SystemExit("Failed to update __version__ in dexter_flask/__init__.py")
init_py.write_text(txt2, encoding="utf-8")
PY
  git add pyproject.toml dexter_flask/__init__.py
  git commit -m "Bump version to ${VERSION}"
fi

# Create tag
git tag "$TAG"

# Push tag
git push origin "$TAG"

# Create GitHub release
echo -e "$BODY" | gh release create "$TAG" \
  --title "Dexter ${VERSION}" \
  --notes-file -

echo ""
echo "Released ${TAG}: https://github.com/virattt/dexter/releases/tag/${TAG}"
