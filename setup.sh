#!/bin/bash
# VibeUtopia 根目录入口：转发到 scripts/setup.sh
exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/setup.sh" "$@"
