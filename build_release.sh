#!/usr/bin/env bash


set -euo pipefail


VERSION_FILE="VERSION"
CHANGELOG_FILE="CHANGELOG.md"
DEFAULT_BUMP="patch"


confirm() {
  local prompt="${1:-Are you sure?}"
  read -r -p "⚠️ ${prompt} (y/N): " choice
  case "$choice" in
    y|Y) return 0 ;;
    *) echo "❌ Skipped: ${prompt}"; return 1 ;;
  esac
}


require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "❌ Required command not found: $cmd"
    exit 1
  fi
}


get_current_branch() {
  local branch
  branch="$(git branch --show-current 2>/dev/null || true)"


  if [ -z "$branch" ]; then
    branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  fi


  if [ -z "$branch" ] || [ "$branch" = "HEAD" ]; then
    echo "❌ Could not determine current branch. Are you in a detached HEAD state?"
    exit 1
  fi


  echo "$branch"
}


bump_version() {
  local version="$1"
  local type="$2"
  local major minor patch


  version="${version#v}"


  if ! [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "❌ Invalid version format in ${VERSION_FILE}: v${version}"
    exit 1
  fi


  IFS='.' read -r major minor patch <<< "$version"


  case "$type" in
    major)
      major=$((major + 1))
      minor=0
      patch=0
      ;;
    minor)
      minor=$((minor + 1))
      patch=0
      ;;
    patch)
      patch=$((patch + 1))
      ;;
    *)
      echo "❌ Invalid bump type: $type"
      echo "Usage: $0 [major|minor|patch]"
      exit 1
      ;;
  esac


  echo "v${major}.${minor}.${patch}"
}


get_commits_since_last_tag() {
  local last_tag commits


  last_tag="$(git describe --tags --abbrev=0 2>/dev/null || true)"


  if [ -n "$last_tag" ]; then
    commits="$(git log --pretty=format:"- %s" "${last_tag}..HEAD" 2>/dev/null || true)"
  else
    commits="$(git log --pretty=format:"- %s" 2>/dev/null || true)"
  fi


  if [ -z "$commits" ]; then
    commits="- Minor updates"
  fi


  echo "$commits"
}


update_changelog() {
  local version="$1"
  local date_str="$2"
  local commits="$3"
  local tmp_file


  [ -f "$CHANGELOG_FILE" ] || touch "$CHANGELOG_FILE"


  tmp_file="$(mktemp)"


  {
    printf "## %s (%s)\n" "$version" "$date_str"
    printf "%s\n\n" "$commits"
    cat "$CHANGELOG_FILE"
  } > "$tmp_file"


  mv "$tmp_file" "$CHANGELOG_FILE"
}


main() {
  require_cmd git
  require_cmd gh


  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "❌ This is not a Git repository."
    exit 1
  fi


  local bump_type current_version new_version current_branch date_str commits


  bump_type="${1:-$DEFAULT_BUMP}"
  current_branch="$(get_current_branch)"


  [ -f "$VERSION_FILE" ] || echo "v0.0.0" > "$VERSION_FILE"
  current_version="$(tr -d '[:space:]' < "$VERSION_FILE")"
  new_version="$(bump_version "$current_version" "$bump_type")"


  echo "🌿 Current branch: $current_branch"
  echo "🔼 Version: $current_version → $new_version"


  echo "$new_version" > "$VERSION_FILE"


  date_str="$(date +"%Y-%m-%d")"
  commits="$(get_commits_since_last_tag)"
  update_changelog "$new_version" "$date_str" "$commits"


  echo "📝 Changelog updated"


  if confirm "Commit changes on branch '$current_branch'?"; then
    git add "$VERSION_FILE" "$CHANGELOG_FILE"
    git commit -m "Release $new_version" || echo "⚠️ Nothing to commit"
  fi


  if confirm "Push current branch '$current_branch' to origin?"; then
    git push -u origin "$current_branch"
  fi


  if confirm "Create & push tag $new_version?"; then
    git tag "$new_version"
    git push origin "$new_version"
  fi


  if confirm "Create GitHub release for $new_version from '$current_branch'?"; then
    gh release create "$new_version" \\
      --title "$new_version" \\
      --generate-notes \\
      --target "$current_branch"
  fi


  echo "✅ Done: $new_version on branch $current_branch"
}


main "$@"
