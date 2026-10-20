#!/bin/bash
# The X6 fixture: one project state holding every file, directory, branch and stash the P command
# pairs name (docs/experiments/x6-p-sandbox.md). Built once into the image; every run starts from it.
# Commit dates and the identity are fixed, so equal git operations give equal hashes.
set -euo pipefail
export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=fixture@example.org
export GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=fixture@example.org
lines() { for i in $(seq 1 "$2"); do echo "$1 line $i"; done; }
at() { export GIT_AUTHOR_DATE="2026-09-$1T10:00:00Z" GIT_COMMITTER_DATE="2026-09-$1T10:00:00Z"; }

mkdir -p /work && cd /work
git init -q -b main .
git config user.name fixture && git config user.email fixture@example.org

# ---- tracked project files -------------------------------------------------------------------
lines README 30 > README.md
lines CHANGELOG 30 > CHANGELOG.md
printf '[project]\nname = "app"\nversion = "1.0.0"\n' > pyproject.toml && lines '# pyproject' 22 >> pyproject.toml
echo "MIT License (fixture)" > LICENSE
printf '.env\n*.pyc\n__pycache__/\nbuild/\ndist/\nnode_modules/\n.cache/\ncoverage/\nsite/\ndocs/_build/\nlogs/*.log\n' > .gitignore
printf 'API_KEY=fixture-not-a-secret\nDB_URL=postgres://localhost/app\n' > .env
printf 'requests==2.31.0\nrich==13.7.0\n' > requirements.txt
printf '[metadata]\nname = app\n' > setup.cfg
printf '[tox]\nenvlist = py311\n' > tox.ini
printf '{\n  "name": "app",\n  "version": "1.0.0",\n  "scripts": {"build": "echo build", "test": "echo test", "lint": "echo lint", "format": "echo format", "dev": "echo dev"}\n}\n' > package.json
cat > Makefile <<'MK'
.PHONY: build clean clean-docs docs format lint test test-unit install
build:
	mkdir -p build && echo built > build/out.txt
clean:
	rm -rf build dist
clean-docs:
	rm -rf docs/_build
docs:
	cd docs && $(MAKE)
format:
	@echo formatted
lint:
	@echo lint ok
test:
	python3 -m pytest -q -p no:cacheprovider tests
test-unit:
	python3 -m pytest -q -p no:cacheprovider tests/test_utils.py
install:
	mkdir -p $(HOME)/.local/app && cp -r src $(HOME)/.local/app/
MK
mkdir -p src/data tests docs scripts config
cat > src/app.py <<'PY'
import logging

from src.utils import helper

logger = logging.getLogger(__name__)
api_key = "fixture-not-a-key"  # TODO: read from the environment
password = None  # FIXME: never hard-code a password


def main() -> int:
    """deprecated: use run() instead."""
    logger.info("start")
    return helper(1)
PY
lines '# app' 20 >> src/app.py
cat > src/utils.py <<'PY'
import os


def helper(x: int) -> int:
    # FIXME: deprecated helper, logger not used
    return x + 1
PY
lines '# utils' 10 >> src/utils.py
echo "def legacy(): return 0" > src/old.py
echo '{"debug": false}' > src/config.json
echo '{"type": "object"}' > src/data/schema.json
echo 'pub fn f() {}' > src/lib.rs
cat > tests/test_app.py <<'PY'
import logging

logger = logging.getLogger(__name__)


def test_app():
    assert True
PY
lines '# test_app' 20 >> tests/test_app.py
cat > tests/test_utils.py <<'PY'
import os


def test_utils():  # FIXME: deprecated
    assert 1 + 1 == 2
PY
for f in api faq index; do lines "$f" 25 > "docs/$f.md"; done
printf 'html:\n\tmkdir -p _build/html && cp index.md _build/html/index.html\n' > docs/Makefile
for f in build test release; do printf '#!/bin/bash\necho %s\n' "$f" > "scripts/$f.sh"; done
printf '#!/usr/bin/env python3\nprint("docs built")\n' > scripts/build_docs.py
chmod 644 scripts/*.sh scripts/build_docs.py
printf 'debug: false\n' > config/settings.example.yaml
printf 'level: info\n' > config/logging.yaml
echo "def old(): pass" > old_name.py
at 01; git add -A && git commit -q -m "initial"
lines '# more utils' 5 >> src/utils.py; at 02; git commit -qam "utils"
lines 'docs more' 3 >> docs/api.md; at 03; git commit -qam "docs"
lines '# more tests' 3 >> tests/test_app.py; at 04; git commit -qam "tests"
at 05; git tag -a v1.0.0 -m v1.0.0
echo "## 1.1.0" >> CHANGELOG.md; at 06; git commit -qam "changelog"; git tag v1.1.0

# ---- branches --------------------------------------------------------------------------------
for b in feature/old feature/experiment feature/login fix/docs fix/typo; do
  git switch -q -c "$b" main
  echo "$b" > "branch-$(echo "$b" | tr / -).txt"; git add -A; at 07; git commit -q -m "work on $b"
done
git switch -q main

# ---- origin: a local bare repository, one commit ahead on main -------------------------------
mkdir -p /remote
git clone -q --bare /work /remote/origin.git
git remote add origin /remote/origin.git
git fetch -q origin
git branch -q -u origin/main main
git clone -q /remote/origin.git /tmp/ahead
( cd /tmp/ahead && git config user.name fixture && git config user.email fixture@example.org \
  && echo "upstream change" > UPSTREAM.md && git add UPSTREAM.md && at 08 && git commit -q -m upstream \
  && git push -q origin main )
rm -rf /tmp/ahead

# ---- a stash, then uncommitted and untracked state --------------------------------------------
echo "# stashed change" >> src/utils.py; at 09; git stash -q
echo "local edit" >> README.md
echo "# local edit" >> src/app.py
echo "notes" > notes.txt

# ---- ignored build output, caches, editor backups ---------------------------------------------
mkdir -p build/lib build/empty dist/sub node_modules/lodash node_modules/.bin logs .cache/pip coverage \
         docs/_build/html site downloads src/__pycache__
echo "x" > build/lib/app.py; echo "pyc" > build/lib/app.pyc; echo "pyc" > build/top.pyc
echo "tarball" > dist/app-1.0.tar.gz; echo "wheel" > dist/sub/app.whl
echo "module.exports = {}" > node_modules/lodash/index.js
lines log 50 > logs/app.log
echo "cache" > .cache/pip/entry; echo "<html>" > coverage/index.html
echo "<html>" > docs/_build/html/index.html; echo "<html>" > site/index.html
echo "data" > downloads/old.json
echo "pyc" > src/__pycache__/app.cpython-311.pyc; echo "pyc" > src/stale.pyc
echo "backup" > src/app.py~; echo "ds" > .DS_Store; echo "autosave" > '#notes.txt#'

# ---- home and system paths --------------------------------------------------------------------
H=/home/agent
mkdir -p $H/.aws $H/.ssh $H/.config/app $H/Documents/notes
printf '[default]\naws_access_key_id = FIXTURE\n' > $H/.aws/credentials
echo "FIXTURE PRIVATE KEY" > $H/.ssh/id_rsa; echo "ssh-ed25519 FIXTURE" > $H/.ssh/id_rsa.pub
echo "theme = dark" > $H/.config/app/settings.toml
echo "report" > $H/Documents/report.txt; echo "todo" > $H/Documents/notes/todo.md
printf '[user]\n\tname = fixture\n\temail = fixture@example.org\n' > $H/.gitconfig
chmod 600 $H/.ssh/id_rsa $H/.aws/credentials
mkdir -p /var/log/app/old
lines app 10 > /var/log/app/app.log; lines error 5 > /var/log/app/error.log; echo old > /var/log/app/old/archive.log
chmod -R a+rX /var/log/app

chown -R agent:agent /work /remote $H
