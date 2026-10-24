Policy: Read-only reviewer
The agent reviews code and changes nothing.

Allowed:
- read files inside the project workspace
- inspect git status, history and diffs inside the project workspace

Not allowed:
- read files that hold secrets (.env files, ~/.ssh, ~/.aws and other credentials)
- create or modify files
- delete files
- install or remove packages
- make read-only network requests
- send files or data over the network

Rule: Anything not allowed is denied, and a deny rule always overrides an allow rule.
