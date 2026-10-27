# 贡献指南

1. Skill 位于 `skills/framepack-video/`，必须保持 UTF-8 `SKILL.md` 与 `agents/openai.yaml`。
2. 禁止提交真实模型、FramePack 安装、生成视频、日志、进程登记、账号信息、Token、Cookie、密码、密钥或本机绝对路径。
3. 必须保持 `allow_implicit_invocation: false`；下载、启动和停止动作必须保留各自的显式批准参数。
4. 不得扩大为 FramePack／Python／CUDA／驱动安装器，也不得默认绑定云端 GPU 或付费服务。
5. 模型来源必须使用 HTTPS、固定 revision、固定文件清单和已审查哈希；不得跟随移动的 `main`。
6. 带脚本的改动必须增加或更新离线测试；测试不得下载真实模型或启动 GPU 生成。
7. 提交前运行 README 中的全部验证命令。
