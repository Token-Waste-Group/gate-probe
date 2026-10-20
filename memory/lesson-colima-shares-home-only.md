# Lesson: with colima, bind mounts from outside ~ arrive empty

**Type:** lesson (I5, 2026-10-20). **Audience:** every Claude running docker on the laptops, and the reviewer README.

colima shares only the home directory with its VM. A `-v /private/tmp/…:/gateprobe/cache` mount from the scratchpad therefore arrived as an empty directory. The I5 clean-machine check then saw every replayed call as a `replay_miss`, which looks like a broken bundle but isn't. Docker Desktop shares `/Users`, `/tmp` and `/private` by default, so the same command works there.

**How to apply:**
- Put anything you bind-mount under `~`, e.g. a git-ignored `dist/` inside the repo, never the scratchpad.
- If a container sees an empty mount, check the VM's shares before suspecting the data.
- Use `docker --context colima …` explicitly: `docker context use colima` changes the default for everyone on the machine. Stop colima when done (`colima stop`).

See [[reference-dgx-usage]].
