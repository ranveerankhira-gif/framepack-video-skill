# 安全政策

## 支持范围

安全更新优先覆盖最新发布版本。本仓库可发起大型模型下载、管理受控后台下载进程并启动本地 GPU WebUI，因此 Skill 强制显式调用，所有会产生写入、网络、进程或资源消耗的动作都要求本次确认。

## 报告漏洞

请使用 GitHub 的 **Private vulnerability reporting**。不要在公开 Issue 中粘贴真实安装路径、日志、进程登记、模型缓存、账号信息、Token、Cookie、密码或密钥。

## 设计边界

- `status` 只读取用户明确选择的绝对 FramePack 根目录，不搜索其他磁盘。
- 下载只写入该根目录下的受控模型、状态、锁和日志路径；不同内容的最终文件不会被覆盖。
- 模型使用 HTTPS、固定 revision、有限重试、大小与内容哈希验证；失败保留 `.part` 证据。
- 不读取浏览器 Cookie、Hugging Face Token、代理凭据或其他账号文件。
- WebUI 只允许 loopback；Skill 不自动打开浏览器、不自动开始生成。
- 不安装或更新 FramePack、Python、CUDA、驱动或模型，也不静默停止未知进程。
- 约 43 GB 下载与 GPU 运行的磁盘、带宽、电力、时间和可能费用必须由用户逐次确认。
