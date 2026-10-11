FROM ubuntu:24.04
ARG DEBIAN_FRONTEND=noninteractive
ARG LAB_UID=1000
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates coreutils curl dnsutils findutils grep iproute2 iputils-ping \
    netcat-openbsd procps psmisc python3 python3-minimal sed tmux util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid "${LAB_UID}" --create-home --shell /bin/bash redpanda \
    && mkdir -p /workspace \
    && chown redpanda:redpanda /workspace /home/redpanda \
    && chmod 0750 /home/redpanda
ENV HOME=/home/redpanda LANG=C.UTF-8 TERM=xterm-256color PYTHONDONTWRITEBYTECODE=1
WORKDIR /workspace
USER redpanda
CMD ["sleep", "infinity"]
