# gitctx - Git Profile Manager

**gitctx** is a lightweight CLI tool to manage multiple Git profiles and configurations across projects and machines. It lets you create and switch between named profiles, each with its own `.gitconfig` and tracked dotfiles, all versioned in a Git-backed repository stored under `~/.config/gitctx`.

Inspired by tools like [`chezmoi`](https://www.chezmoi.io/) and `git`'s own flexible config system, `gitctx` is ideal for developers with multiple identities (e.g., work/personal), different Git settings, or multiple machines.

---

## Features

* Store and manage multiple named Git profiles
* Keep each profile's `.gitconfig` and tracked dotfiles versioned
* Easily switch between profiles (work, personal, etc.)
* Add and remove files to/from profiles
* Hook support: run custom scripts before or after switching profiles
* Skip hook execution with `--no-hooks`
* Safe: profiles are never auto-applied unless explicitly invoked
* Clone and sync your profile repo from Git remotes
* Optional interactive selection via `fzf`
* Simple and transparent: uses Git under the hood

---

## Installation

1. **Clone the repo** or download `gitctx.py`:

```bash
git clone https://github.com/pixelotes/gitctx.git
cd gitctx
chmod +x gitctx.py
```

2. **(Optional)** Install `fzf` for enhanced interactive selection:

```bash
sudo apt install fzf  # Or use your package manager
```

3. **(Optional)** Create an alias in your .bashrc:

```bash
gitctx="python3 /path/to/gitctx.py"
```

---

## Getting Started

### 1. Initialize

Start a new local config repo or clone an existing one:

```bash
# Start from scratch
gitctx init

# OR clone your existing config repo
gitctx init git@github.com:youruser/gitctx-config.git
```

> Note: If you clone a remote repo, any existing `active_profile` will be unset to prevent overwriting local files.

---

## Example Workflow

### 2. Create Your First Profile from Current Git Config

```bash
gitctx profile add-current personal
```

This copies your current `~/.gitconfig` into the `personal` profile and stores your name/email.

You will be prompted to set it as the active profile.

---

### 3. Add Dotfiles or Hook Scripts to the Profile

```bash
# Add regular files
gitctx file add ~/.gitignore_global
gitctx file add ~/.ssh/config

# Add pre-apply or post-apply hooks (must be executable)
gitctx file add ~/scripts/pre.sh --hook pre-apply
gitctx file add ~/scripts/post.sh --hook post-apply
```

Hook scripts will be executed automatically when switching or applying a profile.

---

### 4. Create a New Empty Profile

```bash
gitctx profile add-new work --user-name "Jane Dev" --user-email jane@company.com
```

This creates a clean Git config using the provided identity.

---

### 5. List Profiles

```bash
gitctx profile list
```

Shows all profiles, their status, creation time, and tracked files.

---

### 6. Switch Between Profiles

```bash
gitctx switch work
```

This applies the files in the `work` profile to your home directory and marks it as active.

To re-apply the current profile:

```bash
gitctx config apply
```

To skip execution of pre/post hooks during switch or apply:

```bash
gitctx switch work --no-hooks
gitctx config apply --no-hooks
```

---

### 7. Edit or Remove Files

```bash
gitctx file edit               # Interactive selection
gitctx file edit gitconfig     # Edit directly

gitctx file rm                  # Remove file interactively
gitctx file rm gitignore_global # Remove specific file
```

---

### 8. Sync with Remote

Push or pull your config repo changes:

```bash
gitctx config push
gitctx config pull
```

You can also inspect profile files:

```bash
gitctx profile inspect personal
```

---

## Commands Overview

### Quick commands

| Command            | Description                                                     |
| ------------------ | --------------------------------------------------------------- |
| `init [repo_url]`  | Initialize or clone a config repository (alias for config init) |
| `switch [profile]` | Apply a profile and set it active (alias for profile switch)    |
| `status`           | Prints the active directory and some relevant stats             |

### Profile Management

| Command               | Description                                   |
| --------------------- | --------------------------------------------- |
| `profile add-current` | Create profile from your current Git config   |
| `profile add-new`     | Create a new profile with provided name/email |
| `profile edit`        | Edit an existing profile                      |
| `profile list`        | List all profiles with details                |
| `profile remove`      | Delete an entire profile                      |
| `profile switch`      | Apply a profile and set it active             |
| `profile inspect`     | List all files in a given profile             |

### File Management

| Command                       | Description                                                    |
| ----------------------------- | -------------------------------------------------------------- |
| `file add [path]`             | Add a file to a profile (uses active if none specified)        |
| `--hook pre-apply/post-apply` | Tag the added file as a pre- or post-hook (must be executable) |
| `file edit`                   | Edit a tracked file in a profile                               |
| `file rm`                     | Remove a file from a profile                                   |

### Configuration Management

| Command                  | Description                             |
| ------------------------ | --------------------------------------- |
| `config init [repo_url]` | Initialize or clone a config repository |
| `config push`            | Push config repo changes                |
| `config pull`            | Pull config repo changes                |
| `config apply`           | Re-apply the current active profile     |
| `--no-hooks`             | Skip execution of pre/post hook scripts |

---

## Hook Support

You can attach executable scripts as pre- or post-apply hooks for a profile:

```bash
gitctx file add ~/scripts/pre-check.sh --hook pre-apply
gitctx file add ~/scripts/post-fix.sh --hook post-apply
```

When switching or applying a profile, `gitctx` will:

* Execute all `pre-apply` scripts **before** applying files
* Execute all `post-apply` scripts **after** applying files

To **skip all hook execution**, use the `--no-hooks` flag:

```bash
gitctx profile switch personal --no-hooks
gitctx config apply --no-hooks
```

---

## Safety First

* `gitctx` **never auto-applies** a profile when cloning.
* It will **not overwrite** your home files unless you explicitly run `switch` or `apply`.
* Hook scripts must be executable or they will be rejected on addition.
* All profile data lives under `~/.config/gitctx`.

---

## Contributing

Pull requests are welcome! For major changes, open an issue first to discuss ideas.

---

## License

[MIT](./LICENSE)

---

## Inspiration

Inspired by [`chezmoi`](https://www.chezmoi.io/) — a tool for dotfile management. `gitctx` takes the same idea and focuses it specifically on Git profile and identity management.
