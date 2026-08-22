# New machine setup: Python venv and GitHub sign-in

Step-by-step instructions for getting the temple product pipeline running on a Mac that has never touched it. This covers the two machine-local pieces that do not sync through iCloud: the Python virtual environment (step 3 of the setup checklist) and the GitHub sign-in (step 4).

**Before you start**, the other two pieces should already be done: the Mac is signed into your Apple ID with iCloud Drive syncing the `1. Peculiar People` folder, and Claude Code is installed and signed in. Give iCloud time to finish downloading before doing anything below.

---

## Step 3: Python 3.12 and the virtual environment

The pipeline runs on Python 3.12 (3.12.8 today). Use 3.12 specifically, not whatever is newest. The requirements file pins exact package versions that ship prebuilt for 3.12; a newer Python can force pip to compile them from source, which fails without extra tooling.

### 3.1 Make sure the iCloud folder is fully downloaded

iCloud likes to leave files in the cloud as placeholders until something opens them. A placeholder looks present in Finder but breaks scripts.

1. In Finder, go to iCloud Drive and find the `1. Peculiar People` folder.
2. Right click it and choose **Keep Downloaded**.
3. Wait for the little cloud icons to disappear, then confirm from Terminal that nothing is still a placeholder:

```bash
find "$HOME/Library/Mobile Documents/com~apple~CloudDocs/1. Peculiar People" -name "*.icloud" | head
```

No output means everything is local. If filenames print, wait and re-run.

### 3.2 Install Python 3.12

Pick one route. Route A is what the Mac mini used in August 2026 and is now the preferred one.

**Route A, uv (fastest, and pins the exact patch version):**

```bash
brew install uv
uv python install 3.12.8
```

Confirm it landed:

```bash
uv python find 3.12.8
```

Expected: a path under `~/.local/share/uv/python/cpython-3.12.8-...`. uv keeps its interpreters in its own directory, so this never collides with the system Python or with anything Homebrew installed. It is also the only route that gives you 3.12.8 exactly, matching `.python-version`.

**Route B, python.org installer:**

1. Go to https://www.python.org/downloads/ and download the latest **3.12.x** macOS installer (scroll past newer versions if needed).
2. Run the installer with the defaults.
3. Confirm it landed:

```bash
python3.12 --version
```

Expected: `Python 3.12.x`.

**Route C, Homebrew (if the machine already uses brew):**

```bash
brew install python@3.12
```

Then confirm:

```bash
$(brew --prefix python@3.12)/bin/python3.12 --version
```

If `python3.12` is not on your PATH after a brew install, use the full `$(brew --prefix python@3.12)/bin/python3.12` in the next step; everything after venv creation is identical.

### 3.3 Create the venv

The venv must be named exactly `.venv.nosync` and sit in the repo root. The `.nosync` suffix is what tells iCloud to leave it alone; renaming it would push thousands of package files into iCloud sync.

With uv (Route A):

```bash
cd "$HOME/Library/Mobile Documents/com~apple~CloudDocs/1. Peculiar People/Claude Projects/temple-product-generator" && uv venv --python 3.12.8 --seed .venv.nosync
```

The `--seed` flag matters: it puts `pip` inside the venv. uv omits pip by default, and every command in these docs calls `./.venv.nosync/bin/pip` directly.

With a python.org or Homebrew install (Routes B and C):

```bash
cd "$HOME/Library/Mobile Documents/com~apple~CloudDocs/1. Peculiar People/Claude Projects/temple-product-generator" && python3.12 -m venv .venv.nosync
```

### 3.4 Install the dependencies

```bash
cd "$HOME/Library/Mobile Documents/com~apple~CloudDocs/1. Peculiar People/Claude Projects/temple-product-generator" && ./.venv.nosync/bin/pip install --upgrade pip && ./.venv.nosync/bin/pip install -r requirements.txt
```

Every dependency (numpy, pillow, python-dotenv, requests, resvg_py, vtracer) installs as a prebuilt wheel on Python 3.12. If pip starts printing compiler output or errors about "building wheel", the Python version is wrong; recheck 3.2.

The Alata font and the tracer script are inside the repo, so there is nothing else to install. The `.env` with the Printify and Shopify tokens synced in with the folder.

### 3.5 Verify

Offline test first (no network, proves Python and the repo are intact):

```bash
cd "$HOME/Library/Mobile Documents/com~apple~CloudDocs/1. Peculiar People/Claude Projects/temple-product-generator" && ./.venv.nosync/bin/python tests/test_publish_drafts.py
```

Expected: `all tests passed`.

Then a read-only live check (proves the tokens in .env work from this machine):

```bash
cd "$HOME/Library/Mobile Documents/com~apple~CloudDocs/1. Peculiar People/Claude Projects/temple-product-generator" && ./.venv.nosync/bin/python generate.py --sweep --report-only
```

Expected: the normal coverage report. If it errors about a missing token, the `.env` file has not synced yet; check 3.1.

### 3.6 The second repo

`temple-ref-finder` is a separate repo in the same folder with its own venv, same
Python, same naming rule. It needs no API keys.

```bash
cd "$HOME/Library/Mobile Documents/com~apple~CloudDocs/1. Peculiar People/Claude Projects/temple-ref-finder" && uv venv --python 3.12.8 --seed .venv.nosync && ./.venv.nosync/bin/pip install -r requirements.txt
```

Verify:

```bash
cd "$HOME/Library/Mobile Documents/com~apple~CloudDocs/1. Peculiar People/Claude Projects/temple-ref-finder" && ./.venv.nosync/bin/python scan.py
```

Expected: a queue report, or `Queue is empty` if nothing is sitting in `../Temples TO DO/`.

---

## Step 4: GitHub sign-in so git push works

Both repos (`temple-product-generator` and `temple-ref-finder`) use the SSH remote
`git@github-peculiar:peculiarmarketing/{repo}.git`. `github-peculiar` is not a real
hostname. It is an alias defined in `~/.ssh/config` that points at github.com and
pins one specific key. That file is machine-local and does not sync through iCloud,
so every new Mac needs it written once.

Everything except `git push` and `git fetch` works without this step.

**Why the alias instead of plain HTTPS:** this Mac is also signed into the work
GitHub account (`edavis821`), which has no access to `peculiarmarketing`. An HTTPS
remote reaches for whatever global credential helper git finds, which is shared with
work repos, so it is possible to authorize the wrong identity without noticing. The
alias carries `IdentitiesOnly yes`, meaning ssh offers that one key and nothing else.
Work credentials are structurally unable to reach these repos.

**4.1 Generate a dedicated key** (no passphrase, so scripts never block on a prompt):

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_peculiar -N "" -C "peculiar-$(hostname -s)"
```

**4.2 Write the alias** into `~/.ssh/config`:

```bash
printf 'Host github-peculiar\n    HostName github.com\n    User git\n    IdentityFile ~/.ssh/id_ed25519_peculiar\n    IdentitiesOnly yes\n' >> ~/.ssh/config && chmod 600 ~/.ssh/config
```

**4.3 Add the public key to GitHub.** Copy it:

```bash
pbcopy < ~/.ssh/id_ed25519_peculiar.pub
```

Then go to https://github.com/settings/keys while signed in as the PERSONAL account
(the one with access to `peculiarmarketing`), click New SSH key, give it the machine's
name as the title, and paste. Authentication key, not signing key.

If the browser is signed into work GitHub, use a private window. Adding the key to the
wrong account is the one mistake here that is quiet: the key is accepted, and the
repos stay invisible.

**4.4 Confirm which account the key landed on:**

```bash
ssh -T github-peculiar
```

Expected: `Hi peculiarmarketing! You've successfully authenticated, but GitHub does not
provide shell access.` If it names any other account, the key went on the wrong one.
Remove it there and redo 4.3.

If it says `Permission denied (publickey)`, the key has not been added yet, or it was
added to an account this alias is not reaching.

**4.5 Test both repos:**

```bash
cd "$HOME/Library/Mobile Documents/com~apple~CloudDocs/1. Peculiar People/Claude Projects/temple-product-generator" && git fetch origin && git push --dry-run
```

```bash
cd "$HOME/Library/Mobile Documents/com~apple~CloudDocs/1. Peculiar People/Claude Projects/temple-ref-finder" && git fetch origin && git push --dry-run
```

Expected: `Everything up-to-date` from each.

Commit identity (`user.name` and `user.email`) is stored per-repo in each `.git/config`,
which does sync through iCloud, so there is nothing to set on a new machine.

### If you would rather use HTTPS

HTTPS works too and needs no key file, but it shares a credential helper with the work
account, which is why it is no longer the arrangement here. If you switch, the remotes
become `https://github.com/peculiarmarketing/{repo}.git`, and you sign in with
`gh auth login --hostname github.com --git-protocol https --web` as the personal
account, verifying with `gh auth status` that it does not say `edavis821`.

Do not do this halfway. A machine with an SSH key but an HTTPS remote ignores the key
entirely and asks for a password instead, and a machine with an HTTPS credential but an
SSH remote fails with `Permission denied (publickey)`. Both failures point at the wrong
cause, which is exactly what this section exists to prevent.

---

## Final checklist

Run down this list; all six green means the machine is fully operational:

1. `./.venv.nosync/bin/python tests/test_publish_drafts.py` prints `all tests passed`
2. `./.venv.nosync/bin/python generate.py --sweep --report-only` prints a coverage report
3. `./.venv.nosync/bin/python scripts/publish_drafts.py --report-only` runs without a token error
4. In `temple-ref-finder`, `./.venv.nosync/bin/python scan.py` prints a queue report
5. `ssh -T github-peculiar` says `Hi peculiarmarketing!`
6. `git push --dry-run` in each repo says `Everything up-to-date`

Two things stay unfinished until you do them by hand, because they need your sign-in:

- **Printify browser login.** The date-layer automation drives your real Chrome through a
  dedicated profile at `.playwright.nosync/chrome-profile`, which is machine-local. Run
  `./.venv.nosync/bin/python scripts/printify_login.py` once and sign in; check it later
  with `--check`. Nothing else in the pipeline needs it, so this can wait until the first
  run that adds date layers.
- **The GitHub public key**, step 4.3 above.

## Troubleshooting

- **`xcrun: error: invalid active developer path`** the first time you run git: macOS needs its command line tools. Run `xcode-select --install`, accept the dialog, retry.
- **`Permission denied (publickey)` on push or fetch**: the public key is not on the account that owns these repos. Run `ssh -T github-peculiar` to see who the key actually authenticates as, then redo 4.3 on the right account.
- **`ssh: Could not resolve hostname github-peculiar`**: `~/.ssh/config` is missing the alias. Redo 4.2. This is the normal state on a brand new Mac, since that file does not sync.
- **git asks for a username and password**: the remote is HTTPS but the machine is set up for SSH. Check with `git remote -v`; it should start with `git@github-peculiar:`. Fix with `git remote set-url origin git@github-peculiar:peculiarmarketing/{repo}.git`.
- **Push is rejected, or the commit shows the wrong GitHub account**: check `git config --local user.email` in the repo. It should be the personal address. `gh auth status` naming `edavis821` is expected and harmless here, since the SSH alias does not consult gh at all.
- **`FileNotFoundError` for something inside the project**: an iCloud placeholder. Redo 3.1.
- **pip compiling or failing to build a package**: wrong Python version. The venv must be built from 3.12. Check with `./.venv.nosync/bin/python -V`, then delete the venv folder (`rm -rf .venv.nosync`) and redo 3.3.
- **`./.venv.nosync/bin/pip: No such file or directory`**: the venv was made with `uv venv` without `--seed`. uv leaves pip out by default. Delete the venv and redo 3.3 with the `--seed` flag.
- **Two machines at once**: do not run the pipeline from two Macs at the same time. The repo's `.git` folder syncs through iCloud, and simultaneous runs can produce iCloud conflict copies inside it. One machine at a time is completely safe.

Remember the Claude Code side is per-machine too: the permission allowlist syncs (it lives in `Claude Projects/.claude/settings.json`), but plugins like superpowers and Claude's accumulated memory do not. The pipeline works without them.
