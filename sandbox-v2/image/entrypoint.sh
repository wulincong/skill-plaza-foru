#!/bin/sh
# 离线沙箱内的 Pi 启动器。运行时长由容器内的 timeout 自行兜底，不依赖 Worker 存活；
# 扩展、技能、模板、主题、上下文文件与项目本地配置的自动发现全部关闭。
set -eu

case "${PI_MAX_SECONDS:-}" in
  '' | *[!0-9]*) echo "plaza-sandbox-pi: PI_MAX_SECONDS 必须是正整数" >&2; exit 125 ;;
esac

mkdir -p /tmp/home /tmp/pi-agent

exec timeout --signal=TERM --kill-after=10 "$PI_MAX_SECONDS" \
  node /opt/pi/node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js \
  --mode rpc --offline \
  --no-extensions --no-skills --no-prompt-templates --no-themes --no-context-files --no-approve \
  --session-dir "${PI_SESSION_DIR:-/work/.pi-sessions}" \
  --name "${PI_SESSION_NAME:-sandbox}"
