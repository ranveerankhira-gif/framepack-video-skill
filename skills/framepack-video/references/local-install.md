# 本地安装与固定模型清单

公开包不安装 FramePack，也不包含模型、GPU 驱动或 CUDA。用户必须先自行取得、审查并安装与自身硬件兼容的 FramePack。

- 根目录：设置 `FRAMEPACK_ROOT`，或向控制器传入绝对 `-Root`。
- WebUI：`<FRAMEPACK_ROOT>\webui`
- 嵌入式 Python：`<FRAMEPACK_ROOT>\system\python\python.exe`
- 可续传模型：`<FRAMEPACK_ROOT>\webui\local_models`
- Hugging Face 缓存：`<FRAMEPACK_ROOT>\webui\hf_download`
- WebUI：仅允许 loopback，默认 `http://127.0.0.1:7860`

控制器不会判断某块 GPU 是否足够。开始生成前，用户需要自行确认显存、CUDA／驱动兼容性、预计运行时间、电力和可能的云端费用。

下载器固定到以下公开仓库 revision，不跟随移动的 `main`：

1. [`hunyuanvideo-community/HunyuanVideo`](https://huggingface.co/hunyuanvideo-community/HunyuanVideo)：`e8c2aaa66fe3742a32c11a6766aecbf07c56e773`
2. [`lllyasviel/flux_redux_bfl`](https://huggingface.co/lllyasviel/flux_redux_bfl)：`45b801affc54ff2af4e5daf1b282e0921901db87`
3. [`lllyasviel/FramePackI2V_HY`](https://huggingface.co/lllyasviel/FramePackI2V_HY)：`86cef4396041b6002c957852daac4c91aaa47c79`

下载前应逐一查看仓库的模型卡、许可证和使用限制。Skill 的 MIT 许可证不替代 FramePack、模型或其依赖的许可证。

Downloader files stored under the FramePack root:

- `framepack-model-download.log`
- `framepack-model-download.err.log`
- `framepack-model-download.process.json`
- `framepack-model-download.lock`（下载器运行时）
- `framepack-model-download.starting.lock`（控制器启动临界区）
- `framepack-model-download.status.json`
- `framepack-model-download.complete`（JSON；全部文件验证后写入）

固定文件总量约 43 GB。下载器调用 `curl.exe`，只接受 HTTPS，最多进行配置次数的重试，并从 `.part` 当前字节数续传。大文件用 SHA-256，小型 Git 文件用 Git blob SHA-1 校验；哈希不符时不覆盖最终文件，也不自动删除证据。
