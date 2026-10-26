# Run from the repo root.
# Step 1 - build the payload, commit main, push
python tools/build_gh_pages.py
git add -A
git commit -m "freshness floor for recall" -m "Ties same-conversation teachings at 1.0 in the recall sort, stops an echo from re-dating a row, and files the fresh-set results with their evidence under docs/evidence/."
git push origin HEAD

# Step 2 - refresh gh-pages via a temp worktree (orphan branch; an in-place
# checkout hits the untracked-overwrite wall against main's working tree)
git worktree add _tmp/gh_worktree gh-pages
Copy-Item -Recurse -Force _tmp/gh_pages/* _tmp/gh_worktree/
git -C _tmp/gh_worktree add -A
git -C _tmp/gh_worktree commit -m "refresh notes and evidence"
git -C _tmp/gh_worktree push origin gh-pages
git worktree remove _tmp/gh_worktree