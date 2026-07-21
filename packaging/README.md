# Packaging manifests

Template manifests for third-party package managers, tracked here so version
bumps are a find-and-replace instead of a from-scratch write. None of these are
consumed automatically — each targets a separate distribution channel with its
own publish step (see
[issue #242](https://github.com/haseeb-heaven/open-agent/issues/242)):

| Directory     | Channel                | Publish mechanism                                                                                                  |
| ------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `scoop/`      | Windows (Scoop)        | Copy `openagent.json` into a separate `scoop-openagent` bucket repo                                                |
| `homebrew/`   | macOS/Linux (Homebrew) | Copy `openagent.rb` into a separate `homebrew-openagent` tap repo                                                  |
| `aur/`        | Arch Linux (AUR)       | Push `PKGBUILD` to `ssh://aur@aur.archlinux.org/openagent.git`                                                     |
| `snap/`       | Ubuntu/Linux (Snap)    | `snapcraft.yaml` lives here as a template; the real one Snapcraft reads must be at repo-root `snap/snapcraft.yaml` |
| `chocolatey/` | Windows (Chocolatey)   | `choco pack` + `choco push` from this directory                                                                    |
| `winget/`     | Windows (winget)       | Copy the three manifest files into a PR against `microsoft/winget-pkgs`                                            |

All files use placeholder values (`<VERSION>`, `<SHA256_...>`) that must be
filled in per release — either by hand or by a future release-automation step.
None of this has been published anywhere yet; publishing requires the relevant
account (npm, Snapcraft, AUR, Chocolatey, Docker Hub) or a PR against an
external repo, so it's a deliberate, separate step from committing these
templates.
