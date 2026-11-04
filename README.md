# March7thAssistantModifiedVer

这是一个基于开源项目 [三月七小助手（March7thAssistant）](https://github.com/moesnow/March7thAssistant) 制作的非官方修改版。

本版本添加了“货币战争刷羁绊”测试脚本：利用三星五费「银狼LV.999」流程进行自动化操作，并在小助手前端加入对应的关卡与停止条件选项。

本仓库遵循原项目的 GPL-3.0 许可证。原项目及其版权归原作者与贡献者所有；本修改版不属于原项目官方发布版本。

## 直接下载安装

普通使用者建议下载打包成品，不需要安装 Python，也不需要虚拟环境。

1. 打开本仓库的 [Releases](https://github.com/ZiqingZhou694/March7thAssistantModifiedVer/releases)。
2. 下载最新版本的完整 ZIP 压缩包。
3. 将 ZIP 完整解压到一个普通文件夹，不要直接在压缩包中运行。
4. 双击 `March7th Launcher.exe`。
5. 首次启动时自行阅读并确认程序提示，然后设置自己的《崩坏：星穹铁道》游戏路径。
6. 在「设置 → 货币战争」中设置银狼脚本的关卡与停止条件，再从任务列表运行“银狼货币战争（测试版）”。

请保留解压后的完整目录，不要只复制单个 EXE。

## 下载源码

可以直接克隆仓库：

```powershell
git clone https://github.com/ZiqingZhou694/March7thAssistantModifiedVer.git
cd March7thAssistantModifiedVer
```

也可以点击 GitHub 页面右上方的 `Code → Download ZIP`，下载后完整解压并进入源码目录。

## 创建并启用虚拟环境

源码要求 Python 3.12 或更高版本，推荐使用 Python 3.14。

在 PowerShell 中创建 `.venv`：

```powershell
py -3.14 -m venv .venv
```

在 PowerShell 中启用虚拟环境：

```powershell
.\.venv\Scripts\Activate.ps1
```

如果使用 CMD，则启用命令为：

```bat
.venv\Scripts\activate.bat
```

命令行前面出现 `(.venv)`，表示虚拟环境已经启用。

## 安装依赖

启用 `.venv` 后执行：

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 运行源码版

启动图形界面：

```powershell
python app.py
```

也可以运行命令行入口：

```powershell
python main.py -h
```

以后再次运行时，只需进入源码目录、重新启用 `.venv`，然后执行 `python app.py`。

本地游戏模式建议使用 Windows PC 客户端，并以 1920×1080 窗口模式运行游戏。自动化脚本仍处于测试阶段，请先观察运行结果并自行承担使用风险。
