#!/bin/bash

VERSION_FILE="VERSION"
CHANGELOG_FILE="CHANGELOG.md"
DEFAULT_BUMP="patch"

confirm() {
  read -p "⚠️ $1 (y/N): " choice
  case "$choice" in
    y|Y ) return 0 ;;
    * ) echo "❌ Skipped: $1"; return 1 ;;
  esac
}

bump_version() {
  local version=$1
  local type=$2

  IFS='.' read -r major minor patch <<< "${version#v}"

  case "$type" in
    major) major=$((major+1)); minor=0; patch=0 ;;
    minor) minor=$((minor+1)); patch=0 ;;
    patch) patch=$((patch+1)) ;;
    *) echo "❌ Invalid bump type"; exit 1 ;;
  esac

  echo "v$major.$minor.$patch"
}

# INIT VERSION
[ ! -f "$VERSION_FILE" ] && echo "v0.0.0" > $VERSION_FILE
CURRENT_VERSION=$(cat $VERSION_FILE)

BUMP_TYPE=${1:-$DEFAULT_BUMP}
NEW_VERSION=$(bump_version "$CURRENT_VERSION" "$BUMP_TYPE")

echo "🔼 Version: $CURRENT_VERSION → $NEW_VERSION"

# UPDATE VERSION FILE
echo "$NEW_VERSION" > $VERSION_FILE

# CHANGELOG
DATE=$(date +"%Y-%m-%d")
COMMITS=$(git log --pretty=format:"- %s" $(git describe --tags --abbrev=0 2>/dev/null)..HEAD)
[ -z "$COMMITS" ] && COMMITS="- Minor updates"

CHANGELOG_ENTRY="\n## $NEW_VERSION ($DATE)\n$COMMITS\n"
echo -e "$CHANGELOG_ENTRY" | cat - $CHANGELOG_FILE > temp && mv temp $CHANGELOG_FILE

echo "📝 Changelog updated"

# =====================
# CONFIRM STEPS
# =====================

if confirm "Commit changes?"; then
  git add .
  git commit -m "Release $NEW_VERSION" || echo "⚠️ Nothing to commit"
fi

if confirm "Push to origin/main?"; then
  git push origin main
fi

if confirm "Create & push tag $NEW_VERSION?"; then
  git tag $NEW_VERSION
  git push origin $NEW_VERSION
fi

if confirm "Create GitHub release?"; then
  gh release create $NEW_VERSION --title "$NEW_VERSION" --generate-notes
fi

echo "✅ Done: $NEW_VERSION"
