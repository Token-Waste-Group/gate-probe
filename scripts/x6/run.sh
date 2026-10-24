#!/bin/bash
# Run one command under strace (file opens, with resolved paths), then print the state snapshot as
# JSON on stdout. The command's own output goes to a file: a gate decides on effect, not on printing.
cd /work
timeout 30 strace -f -qq -yy -e trace=open,openat,openat2 -e signal=none -o /tmp/x6.trace \
  bash -c "$1" > /tmp/x6.out 2>&1 < /dev/null
echo $? > /tmp/x6.status
exec python3 /opt/x6/snapshot.py
