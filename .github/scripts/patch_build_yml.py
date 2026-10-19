#!/usr/bin/env python3
# ruff: noqa: T201
"""为 home-assistant-xin fork 修改 .github/workflows/build.yaml。

从上游 home-assistant/operating-system 同步后、推送到 home-assistant-xin/
operating-system 之前运行。所有 fork 专属修改集中于此，使上游合并无冲突。

脚本幂等：对已 patch 的文件重复运行无副作用。

修改内容：
1.  build job checkout 后插入 "Set source" 步骤调用 patch_china_acceleration.py
2.  home-assistant/actions/helpers/ → home-assistant-xin/actions/helpers/（3 处）
3.  home-assistant/operating-system → home-assistant-xin/operating-system（3 处：
    check_publish 仓库检查、update_index 工作流引用、bump_version 条件）
4.  默认构建从 dev 改为 stable channel：hassio_channel 默认值 default→stable，
    跳过 dev 版本号生成（prepare 和 build job 的 Generate development version
    及 Set version suffix 条件增加 inputs.hassio_channel != 'stable'）
5.  插入 cleanup_r2 job：构建后检查 R2 对象存储，保留最新 2 个版本，删除旧版本
6.  test_os_update.py：替换版本 API 地址（推送前持久化，test job 可获取）
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


def patch_set_source_build(content: str) -> str:
    """在 build job checkout 后插入 'Set source' 步骤调用 patch 脚本。"""
    patch_ref = "python3 .github/scripts/patch_china_acceleration.py"
    set_source = (
        "      - name: Set source\n"
        f"        run: {patch_ref}\n"
    )

    if patch_ref in content:
        print("SKIP: 'Set source' already present in build job")
        return content

    build_checkout = (
        "          submodules: true\n"
        "          persist-credentials: false\n"
    )
    if build_checkout not in content:
        print("ERROR: cannot find build job checkout", file=sys.stderr)
        sys.exit(1)

    checkout_end = content.index(build_checkout) + len(build_checkout)
    next_step = content.index("\n      - name: ", checkout_end)
    content = content[:next_step] + "\n" + set_source + content[next_step:]
    print("OK: inserted 'Set source' step in build job")
    return content


def patch_actions_helpers(content: str) -> str:
    """将 action 引用重定向到 home-assistant-xin。"""
    replacements = [
        ("home-assistant/actions/helpers/", "ha-core/actions/helpers/"),
    ]
    total = 0
    for old, new in replacements:
        if old in content:
            count = content.count(old)
            content = content.replace(old, new)
            total += count
            print(f"OK: replaced {old} ({count} replacements)")
    if total == 0:
        if "ha-core/actions/helpers/" in content:
            print("SKIP: actions/helpers already patched")
        else:
            print("ERROR: cannot find any actions/helpers references", file=sys.stderr)
            sys.exit(1)
    return content


def patch_repository_refs(content: str) -> str:
    """将 home-assistant/operating-system 引用替换为 home-assistant-xin/operating-system。"""
    old = "home-assistant/operating-system"
    new = "ha-core/operating-system"
    if old not in content:
        if new in content:
            print("SKIP: repository refs already patched")
            return content
        print("ERROR: cannot find home-assistant/operating-system references", file=sys.stderr)
        sys.exit(1)
    count = content.count(old)
    content = content.replace(old, new)
    print(f"OK: replaced {old} ({count} replacements)")
    return content


def patch_default_stable_channel(content: str) -> str:
    """将默认构建从 dev 改为 stable channel，跳过 dev 版本号生成。"""
    stable_cond = "github.event_name != 'release' && inputs.hassio_channel != 'stable'"

    old1 = "        default: default\n        options:\n          - default\n"
    new1 = "        default: stable\n        options:\n          - default\n"
    if new1 in content:
        print("SKIP: hassio_channel default already stable")
    elif old1 in content:
        content = content.replace(old1, new1, 1)
        print("OK: hassio_channel default changed to stable")
    else:
        print("ERROR: cannot find hassio_channel default", file=sys.stderr)
        sys.exit(1)

    old2 = (
        "      - name: Generate development version\n"
        "        shell: bash\n"
        "        id: version_dev\n"
        "        if: ${{ github.event_name != 'release' }}\n"
    )
    new2 = (
        "      - name: Generate development version\n"
        "        shell: bash\n"
        "        id: version_dev\n"
        "        if: ${{ " + stable_cond + " }}\n"
    )
    if new2 in content:
        print("SKIP: Generate development version condition already patched")
    elif old2 in content:
        content = content.replace(old2, new2, 1)
        print("OK: patched Generate development version condition")
    else:
        print("ERROR: cannot find Generate development version", file=sys.stderr)
        sys.exit(1)

    old3 = (
        "      - name: Set version suffix\n"
        "        if: ${{ github.event_name != 'release' }}\n"
        "        env:\n"
        "          VERSION_DEV: ${{ steps.version_dev.outputs.version_dev }}\n"
    )
    new3 = (
        "      - name: Set version suffix\n"
        "        if: ${{ " + stable_cond + " }}\n"
        "        env:\n"
        "          VERSION_DEV: ${{ steps.version_dev.outputs.version_dev }}\n"
    )
    if new3 in content:
        print("SKIP: prepare Set version suffix condition already patched")
    elif old3 in content:
        content = content.replace(old3, new3, 1)
        print("OK: patched prepare Set version suffix condition")
    else:
        print("ERROR: cannot find prepare Set version suffix", file=sys.stderr)
        sys.exit(1)

    old4 = (
        "      - name: Set version suffix\n"
        "        if: ${{ github.event_name != 'release' }}\n"
        "        env:\n"
        "          VERSION_DEV: ${{ needs.prepare.outputs.version_dev }}\n"
    )
    new4 = (
        "      - name: Set version suffix\n"
        "        if: ${{ " + stable_cond + " }}\n"
        "        env:\n"
        "          VERSION_DEV: ${{ needs.prepare.outputs.version_dev }}\n"
    )
    if new4 in content:
        print("SKIP: build Set version suffix condition already patched")
    elif old4 in content:
        content = content.replace(old4, new4, 1)
        print("OK: patched build Set version suffix condition")
    else:
        print("ERROR: cannot find build Set version suffix", file=sys.stderr)
        sys.exit(1)

    return content


_CLEANUP_R2_JOB = (
    "  cleanup_r2:\n"
    "    name: Cleanup old R2 versions (keep latest 2)\n"
    "    if: ${{ github.event_name != 'release' && needs.prepare.outputs.publish_build == 'true' }}\n"
    "    needs: [ build, prepare ]\n"
    "    runs-on: ubuntu-22.04\n"
    "    steps:\n"
    "      - name: Install AWS CLI\n"
    "        run: pip install 'awscli<1.37.0'\n"
    "\n"
    "      - name: Cleanup old R2 versions\n"
    "        env:\n"
    "          AWS_ACCESS_KEY_ID: ${{ secrets.R2_OS_ARTIFACTS_ID }}\n"
    "          AWS_SECRET_ACCESS_KEY: ${{ secrets.R2_OS_ARTIFACTS_KEY }}\n"
    "          R2_BUCKET: ${{ secrets.R2_OS_ARTIFACTS_BUCKET }}\n"
    "          R2_ENDPOINT: ${{ secrets.R2_OS_ARTIFACTS_ENDPOINT }}\n"
    "        run: |\n"
    "          echo \"Listing all versions in R2...\"\n"
    "          versions=$(aws s3 ls \"s3://${R2_BUCKET}/\" --endpoint-url \"${R2_ENDPOINT}\" \\\n"
    "            | awk '{print $2}' | sed 's|/||' | sort -rV)\n"
    "          echo \"Versions found (newest first):\"\n"
    "          echo \"${versions}\"\n"
    "          count=0\n"
    "          for version in ${versions}; do\n"
    "            count=$((count + 1))\n"
    "            if [ ${count} -le 2 ]; then\n"
    "              echo \"Keeping: ${version}\"\n"
    "            else\n"
    "              echo \"Deleting: ${version}\"\n"
    "              aws s3 rm \"s3://${R2_BUCKET}/${version}/\" \\\n"
    "                --recursive --endpoint-url \"${R2_ENDPOINT}\"\n"
    "            fi\n"
    "          done\n"
)


def patch_cleanup_r2(content: str) -> str:
    """插入 cleanup_r2 job，保留 R2 最新两个版本，删除旧版本。"""
    if "  cleanup_r2:\n" in content:
        print("SKIP: cleanup_r2 job already present")
        return content

    marker = (
        "      CF_PURGE_TOKEN: ${{ secrets.CF_PURGE_TOKEN }}\n"
        "\n"
        "  bump_version:\n"
    )
    if marker not in content:
        print("ERROR: cannot find insertion point for cleanup_r2", file=sys.stderr)
        sys.exit(1)

    replacement = (
        "      CF_PURGE_TOKEN: ${{ secrets.CF_PURGE_TOKEN }}\n"
        "\n"
        + _CLEANUP_R2_JOB
        + "\n"
        "  bump_version:\n"
    )
    content = content.replace(marker, replacement, 1)
    print("OK: inserted cleanup_r2 job")
    return content


def patch_test_os_update(root: Path) -> None:
    """将 test_os_update.py 的版本 API 替换为国内加速地址。

    此修改在推送前执行，持久化到 fork 仓库，test job checkout 时可获取。
    """
    filepath = root / "tests" / "smoke_test" / "test_os_update.py"
    if not filepath.exists():
        print(f"ERROR: {filepath} not found", file=sys.stderr)
        sys.exit(1)

    content = filepath.read_text(encoding="utf-8")
    old = "https://version.home-assistant.io/stable.json"
    new = "https://version.home-assistant.xin/stable.json"
    if new in content:
        print("SKIP: test_os_update.py already patched")
        return
    content = _replace_once(
        content, old, new, "test_os_update: replace version API URL"
    )
    filepath.write_text(content, encoding="utf-8")
    print(f"OK: patched {filepath}")


def main() -> None:
    """对 build.yaml 应用全部 fork 专属补丁。"""
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    filepath = root / ".github" / "workflows" / "build.yaml"

    if not filepath.exists():
        print(f"ERROR: {filepath} not found", file=sys.stderr)
        sys.exit(1)

    content = filepath.read_text(encoding="utf-8")

    content = patch_set_source_build(content)
    content = patch_actions_helpers(content)
    content = patch_repository_refs(content)
    content = patch_default_stable_channel(content)
    content = patch_cleanup_r2(content)
    filepath.write_text(content, encoding="utf-8")
    print(f"OK: patched {filepath}")

    patch_test_os_update(root)


if __name__ == "__main__":
    main()