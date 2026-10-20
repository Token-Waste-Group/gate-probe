# X6 sandbox (docs/experiments/x6-p-sandbox.md): one fixed project state in which both commands of
# a P pair run, each in a fresh container with --network none. Network is needed only to build it.
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      bash coreutils findutils grep gawk sed less git make rsync tar gzip curl wget \
      openssh-client ack rename jq strace sudo python3 python-is-python3 python3-pip python3-venv \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --break-system-packages --no-cache-dir pytest==8.3.2 mypy==1.11.2 \
    && useradd -m -s /bin/bash agent \
    && echo 'agent ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/agent
COPY fixture.sh run.sh snapshot.py /opt/x6/
RUN bash /opt/x6/fixture.sh && chmod 755 /opt/x6/run.sh
USER agent
WORKDIR /work
ENV HOME=/home/agent GIT_EDITOR=true EDITOR=true VISUAL=true PAGER=cat GIT_PAGER=cat LESSHISTFILE=- \
    GIT_TERMINAL_PROMPT=0 GIT_AUTHOR_DATE="2026-10-01T12:00:00Z" GIT_COMMITTER_DATE="2026-10-01T12:00:00Z"
ENTRYPOINT ["/opt/x6/run.sh"]
