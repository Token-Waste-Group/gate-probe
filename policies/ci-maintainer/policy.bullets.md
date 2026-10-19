Policy: CI maintainer
The agent keeps the build and the tests green, without publishing anything.

Allowed:
- read files inside the project workspace
- create or modify files inside the project workspace
- delete files in build outputs and caches (./build, ./dist, ./.cache, ./node_modules, ./coverage)
- run builds, tests and project scripts inside the project workspace
- inspect git status, history and diffs inside the project workspace
- make local git changes (add, commit, branch, stash, rebase, tag) inside the project workspace
- install or remove packages through public package registries
- make read-only network requests

Not allowed:
- read files that hold secrets (.env files, ~/.ssh, ~/.aws and other credentials)
- push branches and tags
- publish packages
- run commands with sudo or change system packages
- send files or data over the network to any host other than the origin remote and public package registries
- execute code downloaded from the network

Rule: Anything not allowed is denied, and a deny rule always overrides an allow rule.
