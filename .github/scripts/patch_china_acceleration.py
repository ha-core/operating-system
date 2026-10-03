#!/usr/bin/env python3
# ruff: noqa: T201
"""构建时为 operating-system 源码打国内加速补丁。

用单一脚本替代所有 sed + GitHub Variables 方案（TIME_SYNCD、VERSION_SOURCE、
OS_GHCR_SOURCE）。处理内容：
1. timesyncd.conf：Cloudflare NTP 替换为阿里云 NTP。
2. haos-supervisor：替换 GHCR 仓库 + 版本 API 地址。
3. hassio.mk：替换版本 API 地址。
4. create-data-partition.sh：替换版本 API 地址。
5. haos-apparmor：替换版本 API 地址。
6. dind-import-containers.sh：替换 GHCR 仓库。
7. daemon.json：添加南大镜像加速 Docker Hub 拉取。
"""
from __future__ import annotations

from pathlib import Path
import sys


def _replace_once(content: str, old: str, new: str, label: str) -> str:
    """精确替换一次，未匹配或多次匹配则报错退出。"""
    if old not in content:
        print(f"ERROR: patch '{label}' did not find expected text", file=sys.stderr)
        sys.exit(1)
    if content.count(old) > 1:
        print(
            f"ERROR: patch '{label}' matched multiple times", file=sys.stderr
        )
        sys.exit(1)
    return content.replace(old, new, 1)



def patch_timesyncd(filepath: Path) -> None:
    """为 timesyncd.conf 替换国内 NTP 服务器。"""
    content = filepath.read_text(encoding="utf-8")

    content = _replace_once(
        content,
        "FallbackNTP=time.cloudflare.com",
        "FallbackNTP=ntp.aliyun.com time.cloudflare.com",
        "timesyncd: add aliyun NTP with cloudflare fallback",
    )

    filepath.write_text(content, encoding="utf-8")
    print(f"OK: patched {filepath}")


def patch_haos_supervisor(filepath: Path) -> None:
    """为 haos-supervisor 打国内加速补丁。

    1. 在 "# Pull in the Supervisor" 前插入镜像替换逻辑：
       Worker /ghcr 端点内部判断地区，CN 返回加速域名，非 CN 返回 ghcr.io
    2. 替换 docker tag 命令：拉取后 tag 回默认镜像名，删除拉取的镜像，恢复变量
    3. 版本 API 地址替换
    """
    content = filepath.read_text(encoding="utf-8")

    content = _replace_once(
        content,
        "    # Pull in the Supervisor\n"
        '    if docker pull "${SUPERVISOR_IMAGE}:${SUPERVISOR_VERSION}"; then\n',
        '    DEFAULT_SUPERVISOR_IMAGE="${SUPERVISOR_IMAGE}"\n'
        '    GHCR_MIRROR=$(curl -sSL https://os-artifacts.home-assistant.xin/ghcr || echo "ghcr.io")\n'
        '    [ -z "${GHCR_MIRROR}" ] && GHCR_MIRROR="ghcr.io"\n'
        '    SUPERVISOR_IMAGE=$(echo "${SUPERVISOR_IMAGE}" | sed "s@ghcr.io@${GHCR_MIRROR}@g; s/home-assistant/ha-core/g")\n'
        "\n"
        "    # Pull in the Supervisor\n"
        '    if docker pull "${SUPERVISOR_IMAGE}:${SUPERVISOR_VERSION}"; then\n',
        "haos-supervisor: insert ghcr mirror before pull",
    )

    content = _replace_once(
        content,
        '        docker tag "${SUPERVISOR_IMAGE}:${SUPERVISOR_VERSION}" "${SUPERVISOR_IMAGE}:latest"\n',
        '        docker tag "${SUPERVISOR_IMAGE}:${SUPERVISOR_VERSION}" "${DEFAULT_SUPERVISOR_IMAGE}:${SUPERVISOR_VERSION}"\n'
        '        docker image rm --force "${SUPERVISOR_IMAGE}:${SUPERVISOR_VERSION}"\n'
        '        docker tag "${DEFAULT_SUPERVISOR_IMAGE}:${SUPERVISOR_VERSION}" "${DEFAULT_SUPERVISOR_IMAGE}:latest"\n'
        '        SUPERVISOR_IMAGE="${DEFAULT_SUPERVISOR_IMAGE}"\n',
        "haos-supervisor: replace docker tag with default image restore",
    )

    content = _replace_once(
        content,
        "curl -s --location https://version.home-assistant.io/stable.json",
        "curl -s --location https://version.smart-assistant.cn/stable.json",
        "haos-supervisor: replace version API URL with timeout",
    )

    filepath.write_text(content, encoding="utf-8")
    print(f"OK: patched {filepath}")


def patch_hassio_mk(filepath: Path) -> None:
    """为 hassio.mk 打国内加速补丁。"""
    content = filepath.read_text(encoding="utf-8")

    content = _replace_once(
        content,
        'HASSIO_VERSION_URL = "https://version.home-assistant.io/"',
        'HASSIO_VERSION_URL = "https://version.smart-assistant.cn/"',
        "hassio.mk: replace version API URL",
    )

    filepath.write_text(content, encoding="utf-8")
    print(f"OK: patched {filepath}")


def patch_create_data_partition(filepath: Path) -> None:
    """为 create-data-partition.sh 打国内加速补丁。"""
    content = filepath.read_text(encoding="utf-8")

    content = _replace_once(
        content,
        'APPARMOR_URL="https://version.home-assistant.io/apparmor_${channel}.txt"',
        'APPARMOR_URL="https://version.smart-assistant.cn/apparmor_${channel}.txt"',
        "create-data-partition: replace version API URL",
    )

    filepath.write_text(content, encoding="utf-8")
    print(f"OK: patched {filepath}")


def patch_haos_apparmor(filepath: Path) -> None:
    """为 haos-apparmor 打国内加速补丁。"""
    content = filepath.read_text(encoding="utf-8")

    content = _replace_once(
        content,
        'APPARMOR_URL="https://version.home-assistant.io/apparmor.txt"',
        'APPARMOR_URL="https://version.smart-assistant.cn/apparmor.txt"',
        "haos-apparmor: replace version API URL",
    )

    filepath.write_text(content, encoding="utf-8")
    print(f"OK: patched {filepath}")


def patch_dind_import(filepath: Path) -> None:
    """为 dind-import-containers.sh 打国内加速补丁。"""
    content = filepath.read_text(encoding="utf-8")

    content = _replace_once(
        content,
        'docker tag "${supervisor}" "ghcr.io/home-assistant/${arch}-hassio-supervisor:latest"',
        'docker tag "${supervisor}" "ghcr.io/ha-core/${arch}-hassio-supervisor:latest"',
        "dind-import-containers: replace GHCR repo",
    )

    filepath.write_text(content, encoding="utf-8")
    print(f"OK: patched {filepath}")



def patch_daemon_json(filepath: Path) -> None:
    """为 daemon.json 添加南大镜像加速 Docker Hub 拉取。"""
    content = filepath.read_text(encoding="utf-8")

    content = _replace_once(
        content,
        '    "ipv6": true\n'
        '}',
        '    "ipv6": true,\n'
        '    "registry-mirrors": ["https://mirrors.nju.edu.cn"]\n'
        '}',
        "daemon.json: add registry-mirrors",
    )

    filepath.write_text(content, encoding="utf-8")
    print(f"OK: patched {filepath}")


def main() -> None:
    """对 operating-system 源码应用全部国内加速补丁。"""
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()

    patch_timesyncd(
        root / "buildroot-external" / "rootfs-overlay" / "etc" / "systemd" / "timesyncd.conf"
    )
    patch_haos_supervisor(
        root / "buildroot-external" / "rootfs-overlay" / "usr" / "sbin" / "haos-supervisor"
    )
    patch_hassio_mk(
        root / "buildroot-external" / "package" / "hassio" / "hassio.mk"
    )
    patch_create_data_partition(
        root / "buildroot-external" / "package" / "hassio" / "create-data-partition.sh"
    )
    patch_haos_apparmor(
        root / "buildroot-external" / "rootfs-overlay" / "usr" / "libexec" / "haos-apparmor"
    )
    patch_dind_import(
        root / "buildroot-external" / "package" / "hassio" / "dind-import-containers.sh"
    )

    patch_daemon_json(
        root / "buildroot-external" / "rootfs-overlay" / "etc" / "docker" / "daemon.json"
    )


if __name__ == "__main__":
    main()