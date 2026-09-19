# 言语康复智能体

面向脑卒中后言语障碍患者的陪伴式言语康复训练 Web 系统。

场景表达的重新开发以[多轮对话训练与评价系统设计](doc/场景表达多轮对话训练与评价系统设计.md)为主设计，以[功能性沟通评价与迭代依据](doc/场景表达功能性沟通评价与迭代依据.md)为评价原则；临床校准与试点评估执行标准见：[场景表达临床校准与试点评估方案](doc/场景表达临床校准与试点评估方案.md)。

当前项目采用模块化单体架构：

- 前端：Vue 3、TypeScript、Vite、Vue Router、Pinia、Axios
- 后端：FastAPI、SQLAlchemy 2.x、Alembic、PostgreSQL
- 文件存储：本地 `storage/`
- AI 能力：通过后端 `backend/app/integrations/` Provider 适配层接入

数字人采用本地 2.5D 回退与可选的阿里云实时云渲染方案；未启用阿里云凭据时不会产生外部调用。

数字人当前采用“可靠的头像陪练”路线：优先使用用户上传头像作为 Static 2D Avatar，不在当前阶段引入 Live2D、3D 或外部真人视频数字人。

## 目录结构

```text
backend/    FastAPI 后端
frontend/   Vue 前端
storage/    本地文件存储目录
doc/        产品、架构、阶段总结和迭代文档
```

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

动态形象 Worker（另开一个终端，默认 mock 模式）：

```powershell
cd backend
```

患者主闭环烟测：

```powershell
cd backend
python scripts/smoke_patient_flow.py
```

前端构建：

```powershell
cd frontend
npm run build
```

数据库迁移：

```powershell
cd backend
alembic upgrade head
```

## 产品化路线

后续开发以以下文档为准：

- `doc/言语康复智能体_产品落地实现路线图.md`
- `doc/言语康复智能体_成熟产品迭代清单.md`
- `doc/言语康复智能体_生产部署指南.md`
- `doc/言语康复智能体_备份恢复手册.md`
- `doc/言语康复智能体_试用与授权说明.md`
- `doc/言语康复智能体_试用账号初始化说明.md`
- `doc/言语康复智能体_试用反馈收集表.md`

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
