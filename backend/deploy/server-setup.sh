#!/usr/bin/env bash
# Free Schoolrun 后端：服务器一键准备（安装 Docker、创建目录、生成 .env）
#
# 用法（在服务器上以 root 或 sudo 执行）：
#   sudo bash server-setup.sh
#
# 可选环境变量：
#   APP_DIR=/opt/freeschoolrun    # 代码存放目录（默认即可）
#
# 本脚本只做"准备"，不会自动启动服务；启动命令在最后打印。

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/freeschoolrun}"
REPO_DIR="$APP_DIR/backend"

log() { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "请用 root 或 sudo 执行：sudo bash server-setup.sh"

if [ -r /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
fi
case "${ID:-}" in
  ubuntu|debian) ;;
  *) warn "当前系统是 ${ID:-未知}，本脚本按 Ubuntu/Debian 编写，请自行调整为 dnf/yum" ;;
esac

log "1/4 安装 Docker（已安装则跳过）"
if command -v docker >/dev/null 2>&1; then
  log "    已安装：$(docker --version)"
else
  apt-get update -y
  apt-get install -y ca-certificates curl
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
  log "    安装完成：$(docker --version)"
fi

log "2/4 创建目录 $REPO_DIR"
mkdir -p "$REPO_DIR"
chmod 755 "$APP_DIR"

log "3/4 检查代码是否已经上传"
if [ ! -f "$REPO_DIR/deploy/docker-compose.yml" ]; then
  warn "未发现 $REPO_DIR/deploy/docker-compose.yml"
  warn "请先把 backend/ 整个目录上传到 $REPO_DIR（或用 git clone），然后重新执行本脚本"
  exit 0
fi

log "4/4 生成 .env"
if [ -f "$REPO_DIR/deploy/.env" ]; then
  log "    .env 已存在，未覆盖"
else
  cp "$REPO_DIR/deploy/.env.production.example" "$REPO_DIR/deploy/.env"
  chmod 600 "$REPO_DIR/deploy/.env"
  warn "已生成 $REPO_DIR/deploy/.env"
  warn "请编辑它：SITE_ADDRESS / ACME_EMAIL / MYSQL_ROOT_PASSWORD / MYSQL_PASSWORD /"
  warn "         ADMIN_PASSWORD / ADMIN_SESSION_SECRET / MOBILE_AUTH_SECRET / RELEASE_PUBLIC_BASE_URL"
fi

cat <<EOF

$(log "准备完成")

下一步：
  1) 编辑环境变量（务必改掉所有“改成…”的占位口令）
       nano $REPO_DIR/deploy/.env
  2) 启动（首次会构建镜像，约 1-3 分钟）
       cd $REPO_DIR/deploy && docker compose up -d --build
  3) 看证书是否签发成功
       docker compose logs -f caddy
  4) 验收
       curl -s https://<你的域名>/api/health
       curl -s https://<你的域名>/api/client-config
  5) 管理后台
       浏览器打开 https://<你的域名>/admin

以后更新代码：cd $REPO_DIR && git pull && cd deploy && docker compose up -d --build api caddy
EOF
