#!/usr/bin/env bash
# 手记 078 · 一次性系统配置：让广场 pi 以低权用户 plaza-sandbox 运行。
#
# 做什么：
#   1. 建系统用户 plaza-sandbox（nologin）与运行组 plaza-run（wlc + plaza-sandbox）
#   2. 把 node+pi 运行时复制到 /opt/plaza-runtime（沙箱用户访问不到 /home/wlc/.nvm）
#   3. 生成包装脚本 /opt/plaza-runtime/bin/pi-sandbox（固定 PATH 后 exec pi）
#   4. 权限布局：/home/wlc 只授沙箱用户穿行 ACL；workspace 归 plaza-run 组可写；
#      web/.env 收紧为 640（修复此前 664 全机可读）并按 ACL 只读放行沙箱用户
#   5. sudoers：wlc 可以免密以 plaza-sandbox 跑包装脚本（env_keep 透传 DEEPSEEK_API_KEY）
#   6. 在 web/.env 追加 PI_SANDBOX_USER / PI_CLI（重启后端生效）
#
# 隔离边界：pi 只能写 web/server/workspace/**；仓库其余与 /home/wlc 只读或不可达；
# MySQL 主凭据仍经 web/.env 可读（与从前一致），只读账号是下一步（见 078 扩展路线）。
#
# 用法：bash scripts/setup-pi-sandbox.sh           # 首次配置（幂等，可重复执行）
#       bash scripts/setup-pi-sandbox.sh --refresh # 重新复制 node+pi 运行时（升级 pi 后）
set -euo pipefail

REPO=/home/wlc/project/skill-plaza-foru
RUNTIME=/opt/plaza-runtime
SBX=plaza-sandbox
GRP=plaza-run
ENV_FILE=$REPO/web/.env

# 提权前先从调用方 shell 捕获 pi 路径（wlc 的 nvm 只在交互 shell 里加载，
# root 侧再 sudo -u wlc 找是找不到的）
if [ "$(id -u)" -ne 0 ]; then
  CALLER_PI="$(command -v pi || true)"
  exec sudo env CALLER_PI="${CALLER_PI:-}" bash "$0" "$@"
fi

say() { printf '\n== %s\n' "$*"; }

# 定位 pi：调用方 shell 的 PATH → nvm 目录（版本最高）→ 系统路径
resolve_pi() {
  case "$CALLER_PI" in /*) [ -x "$CALLER_PI" ] && { echo "$CALLER_PI"; return 0; } ;; esac
  local found
  found="$(ls -v /home/wlc/.nvm/versions/node/*/bin/pi 2>/dev/null | tail -1 || true)"
  [ -n "$found" ] && { echo "$found"; return 0; }
  for p in /usr/local/bin/pi /usr/bin/pi; do
    [ -x "$p" ] && { echo "$p"; return 0; }
  done
  return 1
}
PI_BIN="$(resolve_pi)" || {
  echo '错误：找不到 pi。请在 wlc 的 shell 里直接运行本脚本（pi 可用时），' >&2
  echo '或先确认 nvm 目录：ls /home/wlc/.nvm/versions/node/*/bin/pi' >&2
  exit 1
}
echo "pi 运行时来源：$PI_BIN"
# nvm 的 bin/pi 是指向 node_modules 包内文件的符号链接，不能 readlink 解引用
# （会取到包的 dist 目录）；按 nvm 布局直接取上两级 = node 版本根目录
case "$PI_BIN" in
  /home/wlc/.nvm/versions/node/*/bin/pi) NODE_DIR="$(dirname "$(dirname "$PI_BIN")")" ;;
  *)
    echo "错误：pi 不在 nvm 布局下（$PI_BIN）。本脚本按 nvm 目录复制运行时，" >&2
    echo '请确认 pi 安装方式或调整脚本 NODE_DIR 推导。' >&2
    exit 1
    ;;
esac
[ -x "$NODE_DIR/bin/node" ] || { echo "错误：$NODE_DIR/bin/node 不存在。" >&2; exit 1; }

say "1/7 沙箱用户与运行组（$SBX / $GRP）"
id "$SBX" >/dev/null 2>&1 || useradd --system --create-home --home-dir "/home/$SBX" --shell /usr/sbin/nologin "$SBX"
getent group "$GRP" >/dev/null || groupadd "$GRP"
usermod -aG "$GRP" "$SBX"
usermod -aG "$GRP" wlc

say "2/7 复制 node+pi 运行时：$NODE_DIR -> $RUNTIME"
# 布局不完整（如旧版脚本误拷了包 dist）或 --refresh 时整目录重建，
# 避免残留混入；/opt/plaza-runtime 只归本脚本使用
if [ ! -x "$RUNTIME/bin/node" ] || [ ! -e "$RUNTIME/bin/pi" ] || [ "${1:-}" = "--refresh" ]; then
  rm -rf "$RUNTIME"
  mkdir -p "$RUNTIME"
  cp -a "$NODE_DIR"/. "$RUNTIME"/
fi
[ -x "$RUNTIME/bin/node" ] && [ -e "$RUNTIME/bin/pi" ] || {
  echo "错误：运行时复制不完整（$RUNTIME/bin/node 或 bin/pi 缺失）。" >&2
  exit 1
}
chown -R root:root "$RUNTIME"
chmod -R a+rX "$RUNTIME"

say '3/7 包装脚本 pi-sandbox（sudoers 白名单入口，固定 PATH）'
cat > "$RUNTIME/bin/pi-sandbox" <<'EOF'
#!/bin/sh
# 手记 078：sudo 入口。sudoers 只白名单本脚本；DEEPSEEK_API_KEY 经 env_keep 透传。
export PATH="/opt/plaza-runtime/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
exec /opt/plaza-runtime/bin/pi "$@"
EOF
chown root:root "$RUNTIME/bin/pi-sandbox"
chmod 755 "$RUNTIME/bin/pi-sandbox"

say '4/7 目录权限'
command -v setfacl >/dev/null || { echo '错误：需要 setfacl（sudo apt install acl）。' >&2; exit 1; }
# /home/wlc 是 750：只给沙箱用户穿行权（x），不开 other；仓库各目录 other 本有 r-x
setfacl -m "u:$SBX:x" /home/wlc
# workspace 整树归运行组并组可写；此后新建会话目录由 index.ts 显式 chmod 2775
chgrp -R "$GRP" "$REPO/web/server/workspace"
find "$REPO/web/server/workspace" -type d -exec chmod 2775 {} +

say '5/7 web/.env 收紧 + 沙箱用户只读放行（career-market-query.mjs 需读它）'
chown wlc:users "$ENV_FILE"
chmod 640 "$ENV_FILE"
setfacl -m "u:$SBX:r" "$ENV_FILE"

say '6/7 sudoers 白名单'
cat > /etc/sudoers.d/plaza-pi <<EOF
Defaults!$RUNTIME/bin/pi-sandbox env_keep += "DEEPSEEK_API_KEY"
wlc ALL=($SBX) NOPASSWD: $RUNTIME/bin/pi-sandbox
EOF
chown root:root /etc/sudoers.d/plaza-pi
chmod 440 /etc/sudoers.d/plaza-pi
visudo -cf /etc/sudoers.d/plaza-pi

say '7/7 web/.env 追加开关（重启后端生效）'
touch "$ENV_FILE"
grep -q '^PI_SANDBOX_USER=' "$ENV_FILE" || cat >> "$ENV_FILE" <<EOF

# 手记 078：pi 以低权用户运行（scripts/setup-pi-sandbox.sh 配置）
PI_SANDBOX_USER=$SBX
PI_CLI=$RUNTIME/bin/pi-sandbox
EOF
chown wlc:users "$ENV_FILE"

say '自检'
# 检查失败要报出来而不是让 set -e 静默退出；FAILED 汇总后统一判退出码
FAILED=0
# 必须走包装脚本：pi 的 cli.js 靠 env node 找 node，直调 bin/pi 会因
# 沙箱用户 PATH 无 node 而失败（与服务器真实调用链一致）
if sudo -u "$SBX" "$RUNTIME/bin/pi-sandbox" --version; then :; else
  echo '警告：沙箱用户跑包装脚本失败！' >&2; FAILED=1
fi
# -print -quit 取第一个匹配，不用管道（pipefail 下 head 会致 find SIGPIPE 误杀脚本）
WS_DIR="$(find "$REPO/web/server/workspace" -mindepth 1 -maxdepth 1 -type d -print -quit)"
if [ -n "$WS_DIR" ] && sudo -u "$SBX" test -w "$WS_DIR"; then
  echo "沙箱用户可写 workspace：OK（$WS_DIR）"
else
  echo '警告：沙箱用户不可写 workspace！' >&2; FAILED=1
fi
if sudo -u "$SBX" test -r "$ENV_FILE"; then echo '沙箱用户可读 web/.env：OK'; else
  echo '警告：沙箱用户不可读 web/.env！' >&2; FAILED=1
fi
if sudo -n -u "$SBX" "$RUNTIME/bin/pi-sandbox" --version >/dev/null; then echo 'sudo 免密链路：OK'; else
  echo '警告：sudo 免密链路失败！' >&2; FAILED=1
fi
if sudo -u "$SBX" test -w "$REPO"; then
  echo '警告：沙箱用户对仓库根有写权限，隔离未生效！' >&2; FAILED=1
else
  echo '沙箱用户对仓库根无写权限：OK'
fi
[ "$FAILED" -eq 0 ] || { echo '自检有失败项，见上方警告。' >&2; exit 1; }

echo
echo '完成。重启后端后生效：以 plaza-sandbox 用户跑一条在线对话验证，'
echo '并检查 traces 里该次运行的 agentEnv（见手记 078 验证节）。'
