# 言语康复智能体

面向脑卒中后言语障碍患者的陪伴式言语康复训练 Web 系统。

场景表达以[多轮对话训练与评价系统设计](docs/algorithms/场景表达多轮对话训练与评价系统设计.md)为主设计，以[功能性沟通评价与迭代依据](docs/algorithms/场景表达功能性沟通评价与迭代依据.md)为评价原则；临床校准与试点评估执行标准见[场景表达临床校准与试点评估方案](docs/algorithms/场景表达临床校准与试点评估方案.md)。

当前项目采用模块化单体架构：

- 前端：Vue 3、TypeScript、Vite、Vue Router、Pinia、Axios
- 后端：FastAPI、SQLAlchemy 2.x、Alembic、PostgreSQL
- 文件存储：本地 `storage/`
- AI 能力：通过后端 `backend/app/integrations/` Provider 适配层接入

数字人采用 Provider 适配：当前生产链路支持腾讯云照片数字人、声音复刻和 WebRTC 播放，同时保留 Static 2D 回退与阿里云适配器。外部 Provider 默认关闭；未配置并启用凭据时不会主动发起真实云调用。

## 目录结构

```text
backend/    FastAPI 后端
frontend/   Vue 前端
storage/    本地文件存储目录
docs/       产品、架构、开发、算法、归档和维护文档
tools/      本地联调辅助脚本（不保存下载的二进制）
backups/    受保护的备份与清单
```

详细模块职责见 [代码库指南](docs/architecture/CODEBASE_GUIDE.md)，文档总导航见 [docs/README.md](docs/README.md)，最近一次安全清理记录见 [清理报告](docs/maintenance/CLEANUP_REPORT.md)。

## 环境要求

- Python 3.11 或兼容版本
- Node.js 20 或兼容版本
- npm 或 pnpm
- PostgreSQL

## 后端启动

进入后端目录：

```powershell
cd backend
```

创建并激活虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

安装依赖：

```powershell
pip install -r requirements.txt
```

开发与测试环境再安装：

```powershell
pip install -r requirements-dev.txt
```

复制环境变量示例：

```powershell
Copy-Item .env.example .env
```

编辑 `backend/.env`，至少确认：

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/speech_rehab_agent
SECRET_KEY=dev-only-secret
```

执行数据库迁移：

```powershell
alembic upgrade head
```

如果迁移命令提示 `connection timeout expired` 或无法连接 `localhost:5432`，先确认 PostgreSQL 服务已经启动。Windows 本地开发常见服务名类似：

```powershell
Get-Service | Where-Object { $_.Name -match 'postgres|pgsql' -or $_.DisplayName -match 'PostgreSQL|postgres' }
```

如果看到服务是 `Stopped`，需要在有权限的 PowerShell 中启动，例如：

```powershell
Start-Service -Name postgresql-x64-17
```

服务启动后再执行：

```powershell
alembic upgrade head
```

也可以先运行数据库连通性检查：

```powershell
python scripts/check_database.py
```

启动后端：

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

后端默认地址：

```text
http://127.0.0.1:8000
```

健康检查：

```text
http://127.0.0.1:8000/api/health
```

## 前端启动

进入前端目录：

```powershell
cd frontend
```

安装依赖：

```powershell
npm install
```

启动开发服务器：

```powershell
npm run dev
```

前端默认地址：

```text
http://127.0.0.1:5173
```

Vite 已配置 `/api` 代理到：

```text
http://127.0.0.1:8000
```

## Mock 模式

没有真实 AI 服务密钥时，系统应保持 mock 模式可演示。

默认 Provider：

```env
ASR_PROVIDER=mock
ACOUSTIC_PROVIDER=mock
TTS_PROVIDER=mock
LLM_FEEDBACK_PROVIDER=mock
SPEECH_EVAL_PROVIDER=mock
```

Mock 模式下应能完成：

```text
注册/登录
-> 创建智能体
-> 上传头像和声音样本
-> 进入训练
-> 录音上传
-> 分析反馈
-> 查看训练记录和报告
```

## 场景表达的结构化语义抽取

多轮场景训练默认仍可在 mock 模式下演示对话流程，但不会生成正式自动总分。若要启用带原话证据与置信度的语义抽取，请配置兼容 OpenAI Chat Completions 的服务：

```env
LLM_FEEDBACK_PROVIDER=openai_compatible
LLM_FEEDBACK_API_KEY=你的密钥
LLM_FEEDBACK_BASE_URL=https://你的服务地址/v1
LLM_FEEDBACK_MODEL=你的模型名
```

系统会把 `LLM_FEEDBACK_BASE_URL` 末尾拼接为 `/chat/completions`。健康检查中的 `providers.llm_feedback` 会显示模型配置是否完整；即使配置完整，仍应先用真实音频和治疗师复核验证服务质量。

## 常用命令

后端测试：

```powershell
cd backend
python -m pytest tests
```

后端静态编译与迁移头检查：

```powershell
cd backend
python -m compileall app
alembic heads
```

前端检查：

```powershell
cd frontend
npm run typecheck
npm run test
npm run build
```

数据库迁移：

```powershell
cd backend
alembic upgrade head
```

## 文档入口

当前有效文档以 `docs/` 导航为准：

- [产品文档](docs/product/)
- [架构文档](docs/architecture/)
- [开发与部署](docs/development/)
- [算法与临床依据](docs/algorithms/)
- [历史归档](docs/archive/)
- [维护记录](docs/maintenance/)

开发顺序：

```text
Phase A：当前 MVP 稳定化
Phase B：可靠头像陪练与数字人语音闭环
Phase C：真实语音分析闭环
Phase D：报告、试用和质控闭环
Phase E：隐私、安全和权限闭环
Phase F：部署、监控和运维闭环
Phase G：小规模真实试用与打磨
```

## 重要原则

- 前端不直接调用第三方 AI API。
- 患者、智能体、训练记录独立建模。
- 声音和形象使用前必须确认授权。
- 数据库只保存文件元数据，大文件保存在 `storage/`。
- 过程性监控和能力画像由后端计算。
- 低质量录音和失败分析不应污染能力画像。
