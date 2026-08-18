# New machine setup: Python venv and GitHub SSH

Step-by-step instructions for getting the temple product pipeline running on a Mac that has never touched it. This covers the two machine-local pieces that do not sync through iCloud: the Python virtual environment (step 3 of the setup checklist) and the GitHub SSH key (step 4).

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

## Step 4: SSH key so git push works

The repo's remote is `github-peculiar:peculiarmarketing/temple-product-generator.git`. That `github-peculiar` name is an SSH alias defined in `~/.ssh/config`, pointing at github.com with a dedicated key. Neither the key nor the config syncs through iCloud, so the new machine needs both.

Everything except `git push` works without this step. Do it whenever you want the machine to be able to push.

**Rule that matters:** the key goes on your PERSONAL GitHub account (the one with access to `peculiarmarketing`). Never the work account (edavis821), and never wire this repo to work credentials.

Two options. Option A is recommended: each machine gets its own key, and if a laptop is ever lost you delete just that machine's key on GitHub.

### Option A: new key for this machine (recommended)

**A.1 Generate the key** (replace `macbook-air` with something identifying this machine):

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_peculiar -C "peculiar-people-macbook-air"
```

When it asks for a passphrase, Enter for none, or set one if you prefer (macOS will offer to remember it in the keychain on first use).

**A.2 Add the SSH config block:**

```bash
cat >> ~/.ssh/config <<'EOF'

Host github-peculiar
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_ed25519_peculiar
  IdentitiesOnly yes
EOF
```

The `IdentitiesOnly yes` line matters: it stops ssh from offering other keys on the machine (like a work key) before this one.

**A.3 Copy the public key to the clipboard:**

```bash
pbcopy < ~/.ssh/id_ed25519_peculiar.pub
```

**A.4 Add it on GitHub:** in a browser, sign into the personal account, then Settings, then **SSH and GPG keys**, then **New SSH key**. Title it after the machine (for example "MacBook Air"), paste, save.

**A.5 Test the connection:**

```bash
ssh -T git@github-peculiar
```

First time, it asks whether to trust github.com; type `yes`. Expected result: `Hi <your-username>! You've successfully authenticated, but GitHub does not provide shell access.` That message is success.

**A.6 Test the repo:**

```bash
cd "$HOME/Library/Mobile Documents/com~apple~CloudDocs/1. Peculiar People/Claude Projects/temple-product-generator" && git fetch origin && git push --dry-run
```

Expected: `Everything up-to-date` (or a quiet fetch). Any "Permission denied (publickey)" means the key is not on the right GitHub account or the config block did not take; see troubleshooting below.

### Option B: copy the existing key from the old Mac

Only if you prefer one key everywhere. The private key is a credential; move it by AirDrop or USB stick only, never by email, iCloud, or any chat upload.

**B.1 On the old Mac**, reveal the files (the `.ssh` folder is hidden): in Finder press Cmd+Shift+G and go to `~/.ssh`. AirDrop both `id_ed25519_peculiar` and `id_ed25519_peculiar.pub` to the new Mac.

**B.2 On the new Mac**, move them into place with correct permissions:

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh && mv ~/Downloads/id_ed25519_peculiar ~/Downloads/id_ed25519_peculiar.pub ~/.ssh/ && chmod 600 ~/.ssh/id_ed25519_peculiar && chmod 644 ~/.ssh/id_ed25519_peculiar.pub
```

SSH refuses to use a private key with loose permissions, which is why the chmod matters.

**B.3** Add the same config block as A.2, then run the same tests as A.5 and A.6. No GitHub step needed since the key is already registered.

---

## Final checklist

Run down this list; all four green means the machine is fully operational:

1. `./.venv.nosync/bin/python tests/test_publish_drafts.py` prints `all tests passed`
2. `./.venv.nosync/bin/python generate.py --sweep --report-only` prints a coverage report
3. `ssh -T git@github-peculiar` greets you by username
4. `git push --dry-run` in the repo says `Everything up-to-date`

## Troubleshooting

- **`xcrun: error: invalid active developer path`** the first time you run git: macOS needs its command line tools. Run `xcode-select --install`, accept the dialog, retry.
- **`Permission denied (publickey)`**: the key is not attached to the personal GitHub account, or ssh is not using it. Run `ssh -T git@github-peculiar -v 2>&1 | grep "Offering"` to see which key ssh offered. Confirm the config block exists and has `IdentitiesOnly yes`.
- **`FileNotFoundError` for something inside the project**: an iCloud placeholder. Redo 3.1.
- **pip compiling or failing to build a package**: wrong Python version. The venv must be built from 3.12. Delete the venv folder (`rm -rf .venv.nosync`) and redo 3.3 with `python3.12`.
- **Two machines at once**: do not run the pipeline from two Macs at the same time. The repo's `.git` folder syncs through iCloud, and simultaneous runs can produce iCloud conflict copies inside it. One machine at a time is completely safe.

Remember the Claude Code side is per-machine too: the permission allowlist syncs (it lives in `Claude Projects/.claude/settings.json`), but plugins like superpowers and Claude's accumulated memory do not. The pipeline works without them.
