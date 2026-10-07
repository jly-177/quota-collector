# 额度领取 · 多平台 AI 每日签到中心

一个零依赖的 Python 自托管脚本，把多个 AI 平台的「每日积分 / 活动分」签到聚合到一个手机网页：**后台定时自动签到，手机随时查看状态、可一键补签**。

- 核心服务：[`web_server.py`](web_server.py) —— 单文件 SPA，内置全部 HTML/CSS/JS，部署只需拷这一个文件
- 详细文档：[`docs/README.md`](docs/README.md)

## 支持平台

共 11 个平台：WorkBuddy、百度千帆、MiniMax Code、Qoder、Link AI、WPS 灵犀、Trae Work、Coze 扣子、即梦 AI、OiiOii、华为码道。

> 多数平台可全自动签到；Link AI / OiiOii 因接口强制人机验证，需网页手动签到后在卡片「✅ 我已在网页签到」确认；Qoder 每日 100 Credits 需桌面端手动领；华为为手动卡，支持网页粘贴会话 Cookie 登录。

## 快速开始

> 需 Python 3.8+，**纯标准库，无需 pip 安装任何依赖**。

1. 准备各平台登录凭据（见 [`docs/README.md`](docs/README.md)「配置各平台凭据」）。凭据文件平铺在项目根目录，由 `.gitignore` 忽略。
2. 双击 `start_web.bat` 启动服务，或命令行 `python web_server.py`。
3. 手机与电脑连同一 WiFi，打开 `http://<电脑IP>:8765` 查看状态 / 一键补签。

千帆签到依赖同目录的自建适配服务 `qf_service.py`（见 `start_qf.bat` 与 `docs/README.md`）。

## 安全说明

- 本项目为**自托管工具**，不内置任何账号凭据；**每个使用者需自行捕获各自的登录态**（抓取方式各平台略有差异，见 `docs/README.md`）。
- 凭据从环境变量或根目录同名本地文件读取（优先级：环境变量 > 本地文件），敏感文件已由 `.gitignore` 排除。
- 请勿把个人 Cookie / Token / 设备 ID 提交到公开仓库。

## 目录结构

```
.
├─ web_server.py          ← 核心：HTTP 服务 + 签到中心单页（PAGE 内联全部 HTML/CSS/JS）
├─ wb_icon.py             ← 各平台官方图标（运行时注入 PAGE）
├─ wb_travel.py           ← 派猫猫旅行（WorkBuddy 卡内弹窗）逻辑
├─ wb_growth.py           ← WorkBuddy 成长中心 / 每日任务一键完成
├─ workbuddy_checkin.py   ← 核心签到逻辑（找 token → 查状态 → 签到）
├─ qf_service.py          ← 百度千帆自建适配服务（web_server 的千帆上游）
├─ envconf.py             ← 本地运维脚本统一从 .env 读配置
├─ config.example.json    ← 各平台凭据文件/环境变量说明模板
├─ .env.example           ← 本地环境变量模板（复制为 .env 填自己的值）
├─ start_web.bat          ← 启动网页服务并打印手机访问地址
├─ start_qf.bat           ← 启动千帆适配服务
├─ run_checkin.bat        ← 本机手动跑一次每日签到
├─ trae_capture.js        ← Trae 登录态捕获脚本
├─ capture_wb_token.js    ← WorkBuddy Token 捕获脚本（含 .bat 入口）
├─ huawei/                ← 华为码道工具链（自动签到/会话保活/重登）
├─ qoder_keeper/          ← Qoder 本机守护（自动领取每日 100 Credits）
└─ docs/                  ← 详细文档
```

完整说明见 [`docs/README.md`](docs/README.md)。
