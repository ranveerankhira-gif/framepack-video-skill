# 安全与权限

- **读取**：`status` 只读取用户显式指定的绝对 FramePack 根目录、当前下载脚本、模型目录、状态、marker、日志与受控进程元数据；不搜索其他磁盘或猜测安装路径。
- **写入**：经批准的下载只在该根目录写入 `webui\local_models`、`.part`、状态、锁、进程登记和日志。哈希不同的既有最终文件不会被覆盖。生成输出位置由用户在任务中选择，模型缓存不被复制。
- **网络**：仅 `download -ApproveDownload` 访问用户配置的 HTTPS Hugging Face 端点，并只请求文档所列固定 revision。无批准时下载脚本在路径创建和网络调用前退出。
- **凭据**：不读取浏览器 Cookie、Hugging Face Token、代理凭据或其他账号文件；私有／需登录模型不在支持范围内。端点 URL 禁止嵌入用户名、密码、query 或 fragment。
- **费用与资源**：固定模型约 43 GB，会消耗网络和磁盘；视频生成会占用 GPU、显存、电力与时间，若用户自行连接云端资源还可能产生费用。Skill 不代替模型许可证审查。
- **最终确认**：`status` 只读；下载要求 `-ApproveDownload`；启动 WebUI／GPU 环境要求 `-ApproveGeneration`；停止下载要求 `-ApproveStopDownload`。每次确认只覆盖该次动作。
- **明确不做**：不安装或更新 FramePack、Python、CUDA、驱动或模型；不自动打开浏览器；不自动开始生成；不暴露 WebUI 到局域网；不无限重试；不静默终止已有进程。
