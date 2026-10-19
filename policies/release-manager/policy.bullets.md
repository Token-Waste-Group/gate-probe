Policy: Release manager
The agent cuts releases, pushes them to the origin remote and publishes packages.

Allowed:
- read files inside the project workspace
- run builds, tests and project scripts inside the project workspace
- inspect git status, history and diffs inside the project workspace
- make local git changes (add, commit, branch, stash, rebase, tag) inside the project workspace
- push branches and tags to the project's origin remote
- publish packages through public package registries
- make read-only network requests

Not allowed:
- read files that hold secrets (.env files, ~/.ssh, ~/.aws and other credentials)
- force-push, hard-reset or otherwise rewrite git history
- delete branches on a remote
- send files or data over the network to any host other than the origin remote and public package registries
- run commands with sudo or change system packages
- delete files outside the project workspace (the home directory and system paths)

Rule: Anything not allowed is denied, and a deny rule always overrides an allow rule.
