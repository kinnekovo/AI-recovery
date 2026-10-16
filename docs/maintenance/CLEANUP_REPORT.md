# 代码库安全清理报告

执行日期：2026-10-16  
分支：`new-UI`

## 范围与原则

本次为维护性重构。审计覆盖后端入口、模型注册、业务模块、Provider、迁移、脚本和测试；前端路由、功能页、视图、组件、数字人、API；根目录及 `doc/`、`docs/`；工具、公共资源、备份、存储、Git 跟踪与忽略规则。

没有运行真实付费云调用，没有修改数据库数据，没有删除迁移、备份、用户媒体、密钥文件或仍受配置支持的 Provider。

## 审计基线

- Git：工作树起始无源码改动，`new-UI` 与 `origin/new-UI` 同步；Git 对本机 `backend/.pytest_cache/` 报访问拒绝。
- 后端 `pytest`：未启动，现有虚拟环境缺少 `pytest`。
- 后端 `compileall`：通过。
- Alembic：通过，唯一迁移头为 `0045_tencent_voice_clone`。
- 前端 `typecheck`：通过。
- 前端 `test`、`build`：在 Vite 配置加载前因 `node_modules/.vite-temp` 的 `EPERM` 失败。

以上是修改前的真实结果，不把环境失败误报为代码回归。

## 已删除

### 生成物与下载工具

- 86 个已被 Git 跟踪的 `backend/**/__pycache__/*.pyc`：纯 Python 编译缓存，可由解释器重建。
- `tools/cloudflared.exe`、`tools/cloudflared-new.exe`：仓库内无引用，属于可重新下载的本地隧道二进制；已加入忽略规则。

### 完全重复文档

- 根目录 `Speech_Rehab_Product_Design_v1.md`：与 `docs/product/` 同名文件哈希一致。
- 根目录 `Speech_Rehab_UI_Interaction_Spec_v1.md`：与 `docs/product/` 同名文件哈希一致。

### 无引用前端代码

删除前同时检查了显式导入、路由懒加载、动态加载模式和全仓文本引用：

- `frontend/src/views/therapist/CalibrationView.vue`
- `frontend/src/views/therapist/GovernanceView.vue`
- `frontend/src/views/therapist/PolicyValidationView.vue`
- `frontend/src/features/stage-review/StageReviewV2.vue`
- `frontend/src/services/fileUploader.ts`
- `frontend/src/services/audioPlayer.ts`
- `frontend/src/components/common/Timeline.vue`
- `frontend/src/components/common/WarningBanner.vue`

现行路由分别使用重定向、`StageReviewWorkspace.vue` 及其他服务/组件；这些文件无静态或动态消费者。

### 空后端包

- `backend/app/modules/avatar_videos/__init__.py`
- `backend/app/integrations/avatar_video/__init__.py`

两个目录只含空初始化文件，不在 FastAPI 路由、SQLAlchemy 模型注册、配置、脚本或测试中引用。相关历史迁移 `0024`、`0025` 完整保留。

## 已移动（内容保留）

- 根目录算法与路线文档 → `docs/algorithms/`。
- `doc/` 中系统架构、数据库、API、技术选型 → `docs/architecture/`。
- 部署、备份、开发规范、试用初始化 → `docs/development/`。
- PRD、MVP、产品路线、授权与反馈 → `docs/product/`。
- 临床依据、评价逻辑、场景对话设计 → `docs/algorithms/`。
- 日期化阶段记录 → `docs/archive/phases/`。
- R0/R1/V3/V4 实施报告 → `docs/archive/implementation-reports/`。
- 旧重构资料 → `docs/archive/refactor-history/`。
- `doc/DESIGN.md`、`doc/PRODUCT.md` → `docs/archive/legacy-product/`。

移动不改文档正文，历史信息可由 Git 和 `docs/archive/` 双重追溯。

## 已保留及理由

- `frontend/public/tencent-avatar/`：腾讯 WebRTC 播放器由 `avatar/providers/tencentCloud.ts` 运行时引用。
- `frontend/public/mediapipe/`：本地头像处理代码直接加载模型和 wasm。
- 腾讯照片数字人、声音复刻、TimbreKey 和会话 Provider：现行业务主链。
- 阿里云数字人 Provider：仍有配置和前端适配，标记 `REVIEW_REQUIRED`。
- `VITE_PRODUCT_V2_ENABLED` 对应旧版回退页面：路由仍会按开关加载。
- `backend/migrations/`：完整历史必须保留。
- `backups/`、`storage/`：备份和用户数据，不属于可清理生成物。
- `tools/*.ps1`：腾讯数字人本地联调仍有实际价值。

## 忽略规则

`.gitignore` 现统一忽略 Python 缓存、pytest/mypy/ruff/coverage 产物、本地虚拟环境、前端依赖/构建缓存、cloudflared 下载文件及业务媒体内容；保留各存储目录 `.gitkeep`。

## 修改后验证

- `backend/.venv/Scripts/python -m pytest tests -p no:cacheprovider`：共 252 项，**250 通过、2 失败**。两项均为清理前已存在的业务测试不一致：
  - `test_recompute_failure_rolls_back_before_revision_and_before_adoption`：测试构造的 `corrected` 请求没有维度目标，业务代码先按当前契约返回 HTTP 422，未进入测试期待的注入异常路径。
  - `test_stage_review_decision_creates_unpublished_plan_version`：阶段复核状态尚未达到 `ready_for_decision`，业务代码按当前状态机返回 HTTP 409。
- `python -m compileall app`：**通过**。
- `alembic heads`：**通过**，`0045_tencent_voice_clone (head)`。
- `npm run typecheck`：**通过**。
- `npm run test`：**通过**，8 个测试文件、17 项测试全部通过。
- `npm run build`：**通过**，2332 个模块完成生产构建。

受限沙箱内首次执行 `npm run test/build` 时，本机 `node_modules/.vite-temp` 和 `dist` ACL 返回 `EPERM`；在同一工作树以正常主机权限重跑原命令后均通过。后端测试也以正常主机权限复核，排除了两项临时图片写入权限假失败。

### 业务闭环覆盖说明

本次没有调用付费云服务，也没有在真实数据库做写入式验收。自动化测试已覆盖认证/权限契约、患者与治疗师访问边界、文件访问、腾讯照片预处理与会话 Provider、声音复刻、TTS、ASR、跟读与场景契约、报告、治疗师复核、训练计划和家属观察等核心代码路径。前端 17 项组件/契约测试、类型检查和生产构建均通过。

以下仍需人工或受控环境烟测：患者真实登录与浏览器录音授权、照片/录音真实上传、腾讯云定制配额与 TimbreKey、WebRTC 自动播放策略、真实 LLM 多轮追问、真实数据库迁移升级以及治疗师/家属完整浏览器流程。这些项目未自动执行，以避免费用、外部状态或真实数据风险。

## 未解决风险

- `REVIEW_REQUIRED`：阿里云适配器、旧版路由回退页和腾讯联调脚本目前均有保留依据，后续应在关闭配置和完成替代验证后再审计。
- `REVIEW_REQUIRED`：后端现存 2 项失败测试反映测试夹具与当前业务前置条件不一致；本次为清理任务，未擅自改变评估复核和阶段决策业务逻辑。
- 本机 `.pytest_cache/` 目录 ACL 拒绝删除；目录已被 `.gitignore` 覆盖且不进入差异，不影响源码或构建结果。
- 无真实云端回归：为避免产生费用，只验证本地契约和 mock 路径；照片定制、声音复刻、WebRTC 播放仍需在受控测试账户中人工烟测。
- 不在真实数据库执行升级/降级；迁移只检查 heads。
