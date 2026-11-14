# Push changes to GitHub

[Back to README](../README.md)

This checkout uses branch `main` and remote `origin` pointing to [harilama05/agentic-python-repo-rag-copilot](https://github.com/harilama05/agentic-python-repo-rag-copilot). Run these commands in a PowerShell terminal from the repository root.

## Review and commit

```powershell
git status --short
git branch --show-current
git remote -v
git check-ignore backend/.env
git ls-files -- backend/.env
```

`git check-ignore` should print `backend/.env`; `git ls-files` should print nothing for it. [The ignore rules](../.gitignore) also exclude the virtual environment, runtime repositories, traces and logs. Commit [the environment template](../backend/.env.example) with blank/example credentials, not your local environment file.

Stage and review the changes, including the graph implementation, its scripts/tests and documentation:

```powershell
git add .
git diff --cached --stat
git diff --cached --check
git diff --cached --name-only
git diff --cached
```

If the staged content matches what you want to publish:

```powershell
git commit -m "feat: add runtime call graph evidence and align documentation"
git push origin main
```

Complete GitHub authentication if Git prompts for it. Refresh the repository page to see the new commit and README. This publishes source code; it does not deploy the app or copy Supabase data/model weights to GitHub.

## If the push is rejected

If Git specifically reports `non-fast-forward` or asks you to fetch first, after committing local work:

```powershell
git pull --rebase origin main
git push origin main
```

If the rebase reports conflicts, run `git status`, resolve the listed files, stage those resolved files, and run `git rebase --continue`. `git rebase --abort` returns to the state before the rebase if needed. Do not use force-push to bypass conflicts on `main`.

If Git reports `dubious ownership` for this checkout, run the affected command with a repository-scoped override, for example:

```powershell
git -c safe.directory=D:/Project/agentic-python-repo-rag-copilot/agentic-python-repo-rag-copilot status
```

Replace the final `status` with the intended Git command. This does not change your global Git configuration.
