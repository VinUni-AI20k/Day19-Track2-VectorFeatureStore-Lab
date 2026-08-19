# Day 19 lab — a plain Linux box to run the lab in.
#
# Why: the repo is written for Linux (bash setup scripts, a Makefile that
# hardcodes .venv/bin/...). This image supplies that Linux, nothing more.
# It installs NO lab dependencies — `bash setup-lite.sh` does that, run by hand
# inside the container, exactly as the README intends.
#
# Python 3.12 on purpose: 3.14 would drag in the dill/pyarrow overrides
# described in requirements.txt.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

# make      — the lab's documented interface
# git       — submission flow
# curl      — smoke-testing the API
# build-essential — fallback for any dep without a prebuilt wheel
RUN apt-get update && apt-get install -y --no-install-recommends \
        make git curl ca-certificates build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
EXPOSE 8888 8000

# Pre-create an EMPTY venv at the path setup-lite.sh expects.
#
# Why: docker-compose.lab.yml mounts a named volume over /workspace/.venv so the
# venv lives on the container's Linux filesystem instead of the Windows bind
# mount (~23k small files -- an order of magnitude slower over virtiofs).
# A named volume is initialised from the image content at its mount point, so
# this RUN is what seeds it. Without it the volume would mount as an empty
# directory, setup-lite.sh's `if [ ! -d ".venv" ]` would skip creation, and the
# next line -- `source .venv/bin/activate` -- would kill the script.
#
# No lab dependencies are installed here. setup-lite.sh still does that.
RUN python3 -m venv /workspace/.venv
