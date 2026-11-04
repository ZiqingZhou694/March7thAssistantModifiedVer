# March7thAssistantModifiedVer

这是基于开源项目 [March7thAssistant](https://github.com/moesnow/March7thAssistant) 修改的测试版本，主要加入“银狼货币战争（测试版）”流程及对应前端选项。

## 给普通使用者

请从本仓库的 **Releases** 页面下载打包成品。解压完整文件夹后运行 `March7th Launcher.exe`。

- 不需要安装 Python。
- 不需要创建或激活虚拟环境。
- 不要只复制单个 EXE；`assets`、`libraries`、`3rdparty` 等目录必须保留。
- 首次运行请自行阅读并确认程序提示，然后配置自己的游戏路径和参数。
- 本地游戏模式建议使用 Windows PC 客户端和 1920×1080 窗口模式。

## 给开发者

下载源码并自行运行或打包时，才需要 Python 和虚拟环境。仓库不会包含作者本机的 `venv3145`、`config.yaml`、日志、临时文件、通知 Webhook 或运行记录。

本地打包入口为 `打包_官方流程.cmd`；其中的 Python 虚拟环境路径需要按自己的电脑调整。

## 说明

这是未经上游项目官方支持的修改测试版。自动化工具可能存在识别失败和账号风险，请先小范围测试，并自行承担使用风险。

本项目继承上游的 GPL-3.0 许可证；原项目版权与贡献归原作者及贡献者所有。
