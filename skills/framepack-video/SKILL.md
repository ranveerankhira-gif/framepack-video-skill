---
name: framepack-video
description: 审查并操作用户已安装的本地 FramePack，用于模型状态检查、经确认的固定版本模型下载和图生视频 WebUI 启动。仅在用户明确要求 FramePack 工作时使用；不得隐式下载约 43 GB 模型、安装或更新软件、启动 GPU 生成或消耗付费资源。
---

# FramePack 本地视频生成

运行控制器前读取[安全与权限](references/security-and-permissions.md)。排查安装、模型来源或运行文件时再读取[本地安装说明](references/local-install.md)。

使用随附控制器，不拼接或重建命令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/framepack.ps1 -Action status -Root "<absolute-path-to-framepack>"
```

## 工作流

1. 先运行 `status`。分别报告安装、嵌入式 Python、模型 marker、下载进程、缓存和部分文件状态；marker 缺失、损坏或与当前下载器哈希不一致时，模型不得标为完成。
2. 下载前说明约 43 GB 的网络与磁盘成本，并让用户核对模型页面及许可证。只有得到本次明确批准后才运行 `download -ApproveDownload`。下载器只接受 HTTPS，使用固定 revision、有限重试和 `.part` 文件；文件大小与官方哈希都吻合后才原子落盘。
3. 只有 `modelsComplete: true` 且用户批准本次 GPU 使用时，才运行 `start -ApproveGeneration`。控制器仅绑定 loopback，不自动打开浏览器；服务确认启动后再提示用户自行访问 `http://127.0.0.1:7860`。
4. 需要角色连续性时，可将用户选择的参考图作为首帧，但要说明：FramePack 不保证长视频中的身份完全一致。
5. 生成结果留在用户为当前任务选择的输出目录；不得移动、复制或删除模型缓存。

## 控制器动作

- `status`：只读诊断，不因 Python 缺失而拒绝返回状态。
- `download -ApproveDownload`：在后台下载固定清单；不会安装或更新 FramePack。
- `start -ApproveGeneration`：验证完成 marker 后启动本地 WebUI；不会自动开始生成。
- `stop-download -ApproveStopDownload`：仅在进程路径、启动时间、脚本哈希、根目录和命令行全部匹配时停止已登记下载器；保留 `.part`。

## 边界

- 要求绝对 `-Root` 或 `FRAMEPACK_ROOT`，不得猜测安装路径。拒绝根目录、`webui` 或目标路径中的符号链接／重解析点。
- 不覆盖同名但哈希不同的最终模型。校验失败时保留 `.part` 作为证据并停止，不无限重下。
- 不启动重复下载器或 WebUI，不静默停止已有进程。
- 公开包不包含 FramePack、模型、驱动、登录态或任何本机配置。
