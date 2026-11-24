FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:170fab707454b1350981adcdc2f536ec21f24d06d7f008e8d40064afeacb8a94

ENV NODE_DISABLE_COMPILE_CACHE=1

# tini 作为 PID 1：回收 Pi 工具留下的孤儿进程，并把停止信号转给整个进程组
RUN apt-get update \
 && apt-get install -y --no-install-recommends tini=0.19.0-1+b3 \
 && rm -rf /var/lib/apt/lists/*

COPY pi/package.json pi/package-lock.json /opt/pi/
RUN npm ci --prefix /opt/pi --omit=dev --ignore-scripts --no-audit --no-fund \
 && npm cache clean --force \
 && test "$(PI_CODING_AGENT_DIR=/tmp/pi-check node /opt/pi/node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js --version)" = "$(node -p "require('/opt/pi/package.json').dependencies['@earendil-works/pi-coding-agent']")" \
 && rm -rf /root/.npm /root/.cache /root/.pi /tmp/pi-check /tmp/node-compile-cache

COPY --chmod=0555 entrypoint.sh /usr/local/sbin/plaza-sandbox-pi

RUN groupadd --gid 65532 sandbox \
 && useradd --uid 65532 --gid 65532 --system --no-create-home --home-dir /tmp/home --shell /usr/sbin/nologin sandbox \
 && install -d -o 65532 -g 65532 -m 0700 /work /input

WORKDIR /work
ENV HOME=/tmp/home \
    PI_CODING_AGENT_DIR=/tmp/pi-agent \
    PI_OFFLINE=1 \
    PI_SKIP_VERSION_CHECK=1 \
    PI_TELEMETRY=0
USER 65532:65532
LABEL plaza.sandbox.role="pi"
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/usr/local/sbin/plaza-sandbox-pi"]
CMD []
