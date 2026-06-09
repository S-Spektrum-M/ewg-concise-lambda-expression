FROM ubuntu:24.04

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    make \
    python3 \
    python3-venv \
    python3-pip \
    texlive-xetex \
    texlive-fonts-recommended \
    texlive-latex-recommended \
    texlive-latex-extra \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Clone the wg21 repository, check out the specific commit, and build its dependencies.
# The commit matches the pinned submodule commit in the stdx-posix repo.
RUN git clone https://github.com/mpark/wg21.git /opt/wg21 && \
    cd /opt/wg21 && \
    git checkout dabffb606685a6ed2adcba5459e4866aa494287f && \
    # Build TEST.html and TEST.pdf to trigger downloading pandoc, setting up the python venv,
    # and generating defaults/csl/annex-f dependencies.
    make TEST.html TEST.pdf

WORKDIR /workspace
