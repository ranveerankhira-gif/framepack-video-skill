# FramePack 本地视频生成 Skill

**让 Codex 检查并控制你已经安装好的 FramePack，但下载约 43 GB 模型或使用 GPU 前必须单独确认。**

`framepack-video` 是一个面向 Windows 与 Codex 的显式调用 Skill。它可以只读检查本机安装状态、下载固定 revision 的模型，或启动只绑定回环地址的 WebUI；它不会安装 FramePack、猜测安装路径、自动打开浏览器或直接开始生成。

> Control an existing local FramePack installation from Codex with status checks, pinned model downloads, and loopback-only WebUI startup under explicit approval.

[![Skill](https://img.shields.io/badge/skill-1-2563eb)](#核心能力)
[![Latest release](https://img.shields.io/github/v/release/ranveerankhira-gif/framepack-video-skill?label=release)](https://github.com/ranveerankhira-gif/framepack-video-skill/releases/latest)
[![Validate](https://github.com/ranveerankhira-gif/framepack-video-skill/actions/workflows/validate.yml/badge.svg)](https://github.com/ranveerankhira-gif/framepack-video-skill/actions/workflows/validate.yml)
[![Platform](https://img.shields.io/badge/platform-Windows-0078d4)](#运行要求)
[![Explicit only](https://img.shields.io/badge/invocation-explicit--only-d97706)](#安全边界)
[![License: MIT](https://img.shields.io/badge/license-MIT-16a34a)](LICENSE)

## 先选择你要做的事

| 你的目标 | 使用方式 | 是否产生高成本动作 |
|---|---|---|
| 检查 FramePack、Python、模型和缓存是否就绪 | `status` | 否，只读 |
| 下载固定版本模型并验证大小与哈希 | `download -ApproveDownload` | 是，约 43 GB 网络与磁盘占用 |
| 启动只绑定本机的 WebUI | `start -ApproveGeneration` | 是，需要 GPU、显存、电力和运行时间 |
| 停止由本 Skill 登记且身份完全匹配的下载器 | `stop-download -ApproveStopDownload` | 会终止指定进程 |

**立即使用：**前往 [最新 Release](https://github.com/ranveerankhira-gif/framepack-video-skill/releases/latest)，下载 `framepack-video-<version>.zip`，并用同一页面的 `SHA256SUMS.txt` 核对文件。

## 核心能力

- `status`：只读检查安装、嵌入式 Python、模型 marker、下载进程、缓存和部分文件状态。
- `download -ApproveDownload`：下载约 43 GB 的固定 revision 模型；使用 `.part`、有限重试、大小与哈希验证，并拒绝覆盖不同内容。
- `start -ApproveGeneration`：仅在模型完整且本次得到 GPU 使用批准后启动 WebUI；只绑定 loopback，不自动打开浏览器或开始生成。
- `stop-download -ApproveStopDownload`：仅在进程路径、启动时间、脚本哈希、根目录和命令行全部匹配时停止已登记下载器。

## 安装

1. 从 [GitHub Releases](https://github.com/ranveerankhira-gif/framepack-video-skill/releases/latest) 下载 `framepack-video-<version>.zip`，并核对同一版本的 `SHA256SUMS.txt`。
2. 阅读 `SKILL.md`、`agents/openai.yaml`、脚本和安全说明。
3. 将完整 Skill 目录复制到共享位置：

   ```text
   C:\Users\<你的用户名>\.agents\skills\framepack-video
   ```

4. 重启 Codex，通过 `$framepack-video` 显式调用。

整套仓库下载文件名为 `framepack-video-skill-v0.1.0.zip`。

## 运行要求

- Windows、PowerShell、Python 3.10+；
- 用户已经自行取得、审查并安装的 FramePack；
- 下载模型时约 43 GB 的网络与磁盘空间；
- 生成时由用户自行确认 GPU、显存、驱动、CUDA、电力、运行时间与可能的云端费用。

本仓库不包含 FramePack、模型、驱动、CUDA、登录态或本机配置。MIT 许可证不替代 FramePack、模型或其依赖的许可证。

## 安全边界

- `allow_implicit_invocation: false`，普通视频或创意任务不会自动触发本 Skill。
- 要求用户明确提供绝对 FramePack 根目录；不扫描磁盘或猜测安装位置。
- 下载、启动和停止下载分别要求本次显式确认；批准不能跨动作或跨任务复用。
- 下载只访问用户配置的 HTTPS Hugging Face 端点和文档列出的固定 revision，不读取浏览器 Cookie 或 Hugging Face Token。
- 不安装或更新 FramePack、Python、CUDA、驱动或模型，不自动暴露 WebUI 到局域网。

完整边界见 [`security-and-permissions.md`](skills/framepack-video/references/security-and-permissions.md)。

## 开发与验证

```powershell
python -X utf8 scripts/build_catalog.py
python -X utf8 scripts/validate_repo.py
python -X utf8 scripts/package_release.py --release all --verify-only
python -X utf8 -m unittest discover -s scripts/tests -v
python -X utf8 -m unittest discover -s skills/framepack-video/tests -v
powershell -NoProfile -ExecutionPolicy Bypass -File skills/framepack-video/tests/Test-FramePackController.ps1
python -m compileall -q skills scripts
```

---

如果它帮你把一次大型模型下载或 GPU 启动变成可检查、可确认的操作，欢迎点一个 ⭐，让更多本地 AI 视频用户找到它。
