# CI/CD & Git Best Practices

This document outlines the mandatory workflows and philosophies for maintaining code stability, traceability, and deployment integrity.

## Core Philosophy

**"Stability First, Deployment Second"**

The path to production must always be:
1.  **Stable Source** (Git)
2.  **Verified Change** (Local Test)
3.  **Committed History** (Git Push)
4.  **Deployment** (AWS)

Never bypass Git to deploy "quick fixes" manually. Your source of truth is the repository, not the S3 bucket.

## Git Workflow Standards

### 1. Pre-Work Stability Check
**Before writing a single line of code:**
- **Status Check**: Run `git status` to ensure your working directory is clean.
- **Pull Latest**: Run `git pull origin main` to ensure you are building on the latest stable version.
- **Create Branch**: Always do work in a feature branch.
    ```bash
    git checkout -b feature/descriptive-name
    ```

4.  **Initialize Git & Create Remote Repo (Important!)**
    ```bash
    git init
    git branch -M main
    # Use standard .gitignore
    echo "venv/" >> .gitignore
    echo ".aws-sam/" >> .gitignore
    
    # CRITICAL: Create the remote repository immediately using gh CLI
    # This prevents the "repository not found" error later.
    gh repo create my-project-name --private --source=. --remote=origin
    ```

5.  **Initial Commit**
    ```bash
    git add .
    git commit -m "chore: initial commit"
    git push -u origin main
    ```

### 2. Development & Verification
- **Granular Commits**: Commit logical units of work. Avoid massive "catch-all" commits.
- **Verify Locally**: Run tests, builds, or local servers *before* committing.
    - *Example*: `npm run build` or `sam build` must succeed.
- **No Broken Commits**: Never commit code that breaks the build.

### 3. The Revert Policy
**If a change breaks production or is unwanted:**
- **❌ DO NOT**: Manually edit files to "undo" the change.
- **✅ DO**: Use Git to revert.
    - **Revert a Commit**: `git revert <commit-hash>` (Creates a new commit that inverses the changes).
    - **Discard Uncommitted Changes**: `git checkout -- <filename>` or `git restore <filename>`.
    - **Reset Branch (Careful)**: `git reset --hard origin/main` (Only if you want to trash local work).

**Why?** Manual edits allow human error to creep back in. Git reverts are mechanically precise and leave a trace in history ("Reverted feature X due to bug Y").

### 4. Push & Merge
- **Push**: `git push origin feature/name`.
- **Pull Request (PR)**: Use PRs to merge to `main`. This is the gatekeeper.
- **Squash & Merge**: (Optional but recommended) Squash noisy feature commits into one clean commit on `main`.

## CI/CD Pipeline Philosophy

### Continuous Integration (CI)
*The process of verifying code every time it is saved.*

- **Automated Checks**: Every push should trigger:
    - **Linting**: (e.g., `eslint`, `flake8`) Enforce style.
    - **Building**: Verify the code compiles/bundles.
    - **Testing**: Run unit tests.
- **Blocker**: If CI fails, the merge is blocked. No exceptions.

### Continuous Deployment (CD)
*The process of releasing accepted code to production.*

- **Trigger**: Deployment happens **ONLY** after code is merged to `main`.
- **Automation**: Use tools like GitHub Actions, AWS CodePipeline, or GitLab CI.
- **Idempotency**: Deployment scripts should be safe to run many times without side effects (e.g., `aws s3 sync`).

### Deployment Workflow
1.  **Manual (Legacy)**: `sam build` -> `sam deploy`
2.  **Automated (Recommended)**: Push to `main` -> GitHub Actions deploys to AWS (OIDC).

- **Immutable Artifacts**: Build once, deploy everywhere. Do not rebuild differently for staging vs. production.

## Implementation Guide (Sleet Watch Specific)

### 1. Manual Deployment (Current State)
Even without full automation, mimic the CD process:
1.  **Commit**: Ensure `git status` is clean.
2.  **Build**: `sam build`.
3.  **Push**: `git push origin main`.
4.  **Deploy**: Run the deployment commands documented in `DEPLOYMENT.md`.

### 2. Automated Future (GitHub Actions)
Migrate to the workflow defined in `.github/workflows/deploy.yml`:
1.  **Push to Main**: User merges PR.
2.  **Action Triggers**: GitHub Action spins up.
3.  **Checkout**: Pulls specific commit.
4.  **Build & Sync**: Runs `aws s3 sync`.
5.  **Invalidate**: Clears CloudFront cache.

## Checklist for Every Change

- [ ] **Git Status Clean?** (Am I starting from a stable state?)
- [ ] **On a Branch?** (Am I isolated?)
- [ ] **Local Build Pass?** (Did I break the app?)
- [ ] **Commit Message Clear?** (Will others understand this?)
- [ ] **Push to Git?** (Is code safe in remote?)
- [ ] **Deploy to AWS** (Only after Push).

## Known Quirks & Troubleshooting (Lessons Learned)

During the setup of this project, we identified several non-obvious hurdles. Future setups should account for these:

### 1. The GitHub CLI (`gh`) Advantage
Standard `git push` fails if the remote repository hasn't been created on the GitHub website first.
- **Tip**: Always use `gh repo create <name> --private --source=. --remote=origin` to create the cloud repo directly from your terminal.

### 2. OIDC Authentication (AssumeRoleWithWebIdentity)
OIDC is secure but very strict. If you see "Not authorized to perform sts:AssumeRoleWithWebIdentity":
- **Wildcard Strategy**: The standard `repo:org/repo:ref:refs/heads/main` claim is brittle. We found that using `repo:jupiter-hlaj/*` (org/user wildcard) is the most robust way to handle multiple branches and environment variations in development.
- **Mandatory Audience**: Ensure the IAM condition includes `StringEquals: "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"`.
- **Account ID Match**: Double check that the `AWS_ROLE_ARN` secret in GitHub actually matches the Account ID of the active AWS environment. If you copy/paste from another project, it will fail silently in STS.

### 3. Build Architecture vs. CI Speed
- **The Issue**: Building `arm64` (Graviton) Lambda functions on GitHub's default `x86_64` runners requires Docker emulation (QEMU), which adds 2-5 minutes to every build.
- **The Speed Fix**: Use `x86_64` for development. This aligns the code with the GitHub Build Server, enabling "native" speed (90-second deployments).
- **When to stay with x86_64**:
    *   **Portability**: For pure Python code, there is zero logic difference. Python is interpreted and "recipes" run identically on both Intel and ARM chips.
    *   **Developer Experience**: Fast feedback loops are prioritized during the MVP phase.
- **When to switch back to arm64 (Graviton)**:
    *   **Scale**: At millions of requests, Graviton is ~20% cheaper and often faster per-watt.
    *   **Native Features**: If using specialized ARM-specific hardware instructions (rare for web apps).
- **CRITICAL WARNING**: If the project adds compiled dependencies (libraries with C extensions like NumPy, Cryptography, or Pandas), ensured the build architecture matches the runtime. Mismatching these results in `invalid ELF header` or `Exec format error` in AWS Lambda.

### 4. Dynamic Resource Discovery
Hardcoding S3 bucket names in CI scripts is a "bad smell."
- **The Fix**: Export the bucket name in the `Outputs` section of `template.yaml` (e.g., `FrontendSnapshotBucket`).
- **The Command**: The CI script can then find it dynamically using:
  `aws cloudformation describe-stacks --stack-name <name> --query "Stacks[0].Outputs[?OutputKey=='FrontendSnapshotBucket'].OutputValue" --output text`

### 5. Case Sensitivity & Renaming
**The Problem**: macOS/Windows filesystems are case-insensitive (e.g., `file.py` and `File.py` are the same file), but Git is case-sensitive (treating them as two distinct files).
- **Symptom**: You rename a file locally, but Git doesn't pick up the change, or worse, you end up with two files in the repository (`file.py` and `File.py`).
- **The Fix**: NEVER rename a file just by capitalization in Finder or VS Code.
- **The Protocol**: Use `git mv` to force the rename in the index.
    ```bash
    git mv myfile.py MyFile.py
    ```

