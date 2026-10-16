# 代码库指南

最后更新：2026-10-16

## 总体结构

```text
.
├─ backend/
│  ├─ app/
│  │  ├─ core/             配置、安全、日志与可观测性
│  │  ├─ database/         SQLAlchemy 基础、会话与模型注册
│  │  ├─ modules/          按业务领域组织的 Router/Schema/Service/Model
│  │  └─ integrations/     ASR、TTS、LLM、发音评估、数字人和声音复刻 Provider
│  ├─ migrations/          Alembic 完整迁移历史
│  ├─ scripts/             数据库检查、备份和试用数据维护脚本
│  └─ tests/               后端回归测试
├─ frontend/
│  ├─ src/
│  │  ├─ features/         完整业务工作流页面
│  │  ├─ views/            登录、角色入口及仍需保留的独立/旧版回退页面
│  │  ├─ components/       可复用 UI 组件
│  │  ├─ layouts/          患者、治疗师、家属布局
│  │  ├─ api/              HTTP 客户端与领域 API
│  │  ├─ stores/           Pinia 全局状态
│  │  ├─ avatar/           数字人 Provider、播放与本地头像能力
│  │  ├─ services/         录音等通用浏览器服务
│  │  ├─ utils/            通用纯函数
│  │  └─ types/            跨模块类型
│  └─ public/              腾讯播放器与 MediaPipe 运行资源
├─ docs/                   统一文档入口
├─ storage/                用户媒体存储（仅目录占位符进入 Git）
├─ backups/                受保护的备份及清单
└─ tools/                  腾讯数字人联调辅助脚本
```

## 后端入口与领域

`backend/app/main.py` 是 FastAPI 组合根，只在此注册对外 Router。`backend/app/database/base.py::import_models()` 是 SQLAlchemy 模型注册清单；新增或删除模型时必须同时核对该函数和 Alembic 元数据。

主要领域模块：

- 账户与授权：`auth`、`users`、`consent`、`family`、`therapist`。
- 患者与陪伴者：`agents`、`files`、`avatar_sessions`。
- 训练与评估：`attempts`、`training`、`assessment`、`scoring`、`pronunciation`、`scenario_dialogues`。
- 结果与复核：`evaluations`、`evaluation_runs`、`reports`、`review_workflow`、`profiles`、`profile_v2`。
- 推荐与治理：`policy_v2`、`policy_validation`、`controlled_policy`、`controlled_governance`、`calibration`、`product_v2`。

部分模块只提供模型或内部服务，不一定直接在 `main.py` 注册 Router；不能仅凭“未注册 Router”判断无用。

## Provider 边界

第三方服务必须由后端 `app/integrations/` 调用，前端不保存云密钥：

- `asr/`：语音识别。
- `acoustic_analysis/`、`pronunciation_assessment/`：声学与发音评估。
- `tts/`：文本转语音。
- `llm/`：兼容 Chat Completions 的场景对话与语义抽取。
- `tencent_avatar/`：腾讯云交互会话、文本驱动和 WebRTC 播放。
- `voice_clone/`：声音复刻及 TimbreKey 绑定。
- `aliyun_avatar/`：仍受配置支持的阿里云适配器，当前不得因非默认而删除。

`backend/.env` 只用于本机且被 Git 忽略；新增配置应先进入 `.env.example`，不得把密钥提交到仓库。

## 前端路由与兼容

`frontend/src/router/index.ts` 是页面可达性的权威入口。`VITE_PRODUCT_V2_ENABLED` 控制治疗师新版工作台与旧页面回退；`views/` 中被该开关引用的旧页面仍是运行依赖，不得按目录名或 `V2`/`legacy` 字样删除。

患者训练主链位于 `features/training-session/`；数字人运行代码位于 `avatar/`。腾讯播放器的 `public/tencent-avatar/` 文件和 MediaPipe 的 `public/mediapipe/` 模型/wasm 均有运行时引用，必须随部署产物保留。

## 数据与迁移安全

- `backend/migrations/versions/` 是不可裁剪的历史链，当前头为 `0045_tencent_voice_clone`。
- `storage/` 中的头像、声音样本、训练音频和生成音频是真实业务数据；清理任务只管理 `.gitkeep` 与忽略规则。
- `backups/` 是恢复材料，不参与普通代码清理。
- 禁止在真实数据库上以“验证”为名执行降级、重建、批量删除或迁移回滚。

## 开发验证

```powershell
cd backend
pip install -r requirements-dev.txt
python -m pytest tests
python -m compileall app
alembic heads

cd ../frontend
npm run typecheck
npm run test
npm run build
```

云 Provider 验证必须使用明确授权的测试账户与预算；常规回归采用 mock，不自动调用付费服务。

## REVIEW_REQUIRED

- `backend/app/integrations/aliyun_avatar/`：当前腾讯云为主，但环境配置和前端适配仍保留阿里云能力，未证明可删除。
- `frontend/src/views/` 中的旧版页面：仍被 `VITE_PRODUCT_V2_ENABLED` 回退路径引用。
- `tools/configure-tencent-avatar.ps1`、`tools/run-tencent-avatar-demo.ps1`：仍可用于联调，保留；其下载产物与虚拟环境不进入 Git。
- `backups/`、`storage/`：属于数据/恢复边界，不作为代码冗余处理。
