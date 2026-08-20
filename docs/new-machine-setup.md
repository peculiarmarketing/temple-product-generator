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

Pick one route.

**Route A, python.org installer (simplest):**

1. Go to https://www.python.org/downloads/ and download the latest **3.12.x** macOS installer (scroll past newer versions if needed).
2. Run the installer with the defaults.
3. Confirm it landed:

```bash
python3.12 --version
```

Expected: `Python 3.12.x`.

**Route B, Homebrew (if the machine already uses brew):**

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

---

## Step 4: GitHub sign-in so git push works

The repo's remote is `https://github.com/peculiarmarketing/temple-product-generator.git`, plain HTTPS. Pushing over HTTPS needs a credential stored on the machine, and credentials do not sync through iCloud, so each new Mac needs signing in once.

Everything except `git push` works without this step. Do it whenever you want the machine to be able to push.

**Rule that matters:** sign in as your PERSONAL GitHub account, the one with access to `peculiarmarketing`. Never the work account (edavis821), and never wire this repo to work credentials. This is the one thing to be careful about on a machine where you are also signed into work GitHub, so step 4.3 checks it explicitly.

**4.1 Install the GitHub CLI** if the machine does not have it:

```bash
brew install gh
```

**4.2 Sign in.** This stores a token in the macOS keychain and tells git to use it:

```bash
gh auth login --hostname github.com --git-protocol https --web
```

Answer the prompts: GitHub.com, HTTPS, yes to authenticate git with your GitHub credentials. It opens a browser with a one-time code. Sign into the PERSONAL account in that browser, not the work one. If the browser is already signed into work GitHub, sign out first or use a private window, otherwise you will authorize the wrong account without noticing.

**4.3 Confirm which account you got.** Do not skip this; it is the whole safety check:

```bash
gh auth status
```

Expected: `Logged in to github.com account peculiarmarketing`. If it names `edavis821` or any other account, that is the work account and it must not be used here. Run `gh auth logout`, then redo 4.2 in a private browser window.

**4.4 Test the repo:**

```bash
cd "$HOME/Library/Mobile Documents/com~apple~CloudDocs/1. Peculiar People/Claude Projects/temple-product-generator" && git fetch origin && git push --dry-run
```

Expected: `Everything up-to-date` (or a quiet fetch). Any prompt for a username and password means 4.2 did not take.

### If you would rather use SSH

SSH works too and is slightly stronger about never reaching for work credentials, but it is more setup per machine and the remote would have to change. It is not the current arrangement. If you ever switch, the remote becomes `github-peculiar:peculiarmarketing/temple-product-generator.git`, where `github-peculiar` is an alias in `~/.ssh/config` pointing at github.com with a dedicated key and `IdentitiesOnly yes`. Set it with:

```bash
git remote set-url origin github-peculiar:peculiarmarketing/temple-product-generator.git
```

Do not do this halfway. A machine with an SSH key but an HTTPS remote will ignore the key entirely and ask for a password instead, which is exactly the confusing failure this section exists to prevent.

---

## Final checklist

Run down this list; all four green means the machine is fully operational:

1. `./.venv.nosync/bin/python tests/test_publish_drafts.py` prints `all tests passed`
2. `./.venv.nosync/bin/python generate.py --sweep --report-only` prints a coverage report
3. `gh auth status` says `Logged in to github.com account peculiarmarketing`
4. `git push --dry-run` in the repo says `Everything up-to-date`

## Troubleshooting

- **`xcrun: error: invalid active developer path`** the first time you run git: macOS needs its command line tools. Run `xcode-select --install`, accept the dialog, retry.
- **git asks for a username and password on push**: HTTPS has no stored credential on this machine. GitHub stopped accepting account passwords here years ago, so typing yours will fail. Redo 4.2.
- **Push is rejected, or the commit shows the wrong GitHub account**: you are signed in as the work account. Run `gh auth status` to see which one, then `gh auth logout` and redo 4.2 in a private browser window.
- **`FileNotFoundError` for something inside the project**: an iCloud placeholder. Redo 3.1.
- **pip compiling or failing to build a package**: wrong Python version. The venv must be built from 3.12. Delete the venv folder (`rm -rf .venv.nosync`) and redo 3.3 with `python3.12`.
- **Two machines at once**: do not run the pipeline from two Macs at the same time. The repo's `.git` folder syncs through iCloud, and simultaneous runs can produce iCloud conflict copies inside it. One machine at a time is completely safe.

Remember the Claude Code side is per-machine too: the permission allowlist syncs (it lives in `Claude Projects/.claude/settings.json`), but plugins like superpowers and Claude's accumulated memory do not. The pipeline works without them.
