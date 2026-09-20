# 当前系统资产清单（Phase 0）

## 1. 审计结论摘要

当前系统不是空壳：认证、角色/患者分配、录音存储、训练 session/attempt、真实 ASR 与本地声学 provider、场景多轮对话、正式 assessment metadata、canonical evaluation run、证据质量门、失败审计、可比性、人工复核、不可变画像和受控策略审计均已有实现与测试。

问题主要在产品层：旧页面围绕“选训练/看分数/逐条复核/算法治理”组织；旧 `TrainingPlan` 不是新版正式、版本化计划；事实/观察/建议混合；多个 review 队列没有统一 AttentionItem；患者进展使用未经过统一 comparability gate 的旧趋势。

## 2. 当前技术结构

| 层 | 当前实现 | 状态 |
|---|---|---|
| Web | Vue 3 + TypeScript + Vite | 稳定基础，页面 IA 多数需重写 |
| Routing/state | Vue Router + Pinia | 可保留；training store 不可恢复 |
| HTTP | Axios envelope/error interceptor | 可保留/扩展 aggregate clients |
| API | FastAPI modular monolith | 稳定基础 |
| Domain/application | 模块 service 直接访问 SQLAlchemy | 可工作；领域边界混合 |
| Persistence | SQLAlchemy 2 + PostgreSQL | 稳定资产 |
| Migration | Alembic 0001–0039 单链 | 稳定资产；当前 DB=head |
| Files | 本地 storage + DB metadata | 稳定资产 |
| AI | provider adapters + deterministic engines | 大量可复用，抽象不完全一致 |
| Tests | pytest + Vitest | 全绿 baseline |

## 3. Frontend inventory 与判定

判定含义：KEEP 原样/近原样保留；ADAPT 保留能力与组件，换 contract/presentation；REWRITE 页面结构不适合渐进修补；DEPRECATE 停止产品化维护，兼容期可留路由。

### 3.1 Shell、路由、状态

| 模块 | 判定 | 原因 |
|---|---|---|
| `main.ts`、`App.vue` | KEEP | 标准 composition root，无产品语义 |
| `api/http.ts` | KEEP | token、envelope、错误处理可复用 |
| `stores/auth.ts` | ADAPT | 身份基础稳定；未来加入 onboarding/plan state 应来自 API，不塞进 auth |
| `stores/training.ts` | REWRITE | 仅内存保存 current session/last feedback，不能 pause/resume/reload |
| `router/index.ts` | REWRITE | 患者导航 6+ 项、治疗师 4 项、admin=therapist，均不符新 IA |
| `PatientLayout.vue` | REWRITE | “智能体/能力画像/康复记录”均为旧一级导航 |
| `TherapistLayout.vue` | REWRITE | 缺“训练方案”；阶段评估/系统状态占一级导航 |
| `FamilyLayout.vue` | DEPRECATE from MVP shell | 新规格 MVP 未定义家属端；保留能力但冻结页面 |

### 3.2 患者页面

| 页面/组件 | 判定 | 原因 |
|---|---|---|
| `LoginView.vue` | ADAPT | 认证可保留；视觉与 onboarding redirect 需适配 |
| `HomeView.vue` | REWRITE | 有今日/推荐/最近能力雏形，但主任务不够集中，依赖旧 recommendation 与 agent；缺全部关键状态 |
| `TrainingView.vue` | REWRITE | 仍让患者选择训练类型；新版是连续“今日训练”空间 |
| `TrainingSessionView.vue` | ADAPT substantially | 录音、任务推进、提示、场景对话可复用；缺恢复、组总结、可靠性状态、offline/partial、正式/额外边界 |
| `RecorderPanel.vue`、recorder service | KEEP/ADAPT | 核心录音资产；增加权限/无声预检、持久队列即可 |
| `TrainingResultView.vue` | REWRITE | 仅最后一题、Pinia 临时数据；不是 session summary |
| `ScenarioDialogueResultView.vue` | ADAPT | 患者友好总结不错；应成为 session/组总结一部分 |
| `EvaluationView.vue` | DEPRECATE UI | 与 Report/两个 Profile 页面重复，旧多指标趋势缺统一 comparability |
| `ReportView.vue` | REWRITE into “我的进展” | 能力素材可复用，页面仍是记录/统计驱动 |
| `AbilityProfileView.vue` | DEPRECATE | 旧 AbilityProfile 和抽象等级/置信度，不应作为患者一级页 |
| `PatientProfileView.vue` | ADAPT into progress projection | Profile V2 更可信，但仍是内部画像术语和独立重复页 |
| `AgentCreateView.vue`、`AgentListView.vue` | DEPRECATE standalone pages | 陪伴者能力保留，入口收进“我的”；不再一级 IA |
| `ProcessFeedbackPanel.vue` | REWRITE semantics | Metric、观察、建议仍在一个 result 中 |
| `AvatarCoachPanel.vue` | ADAPT | presentation人格可保留，不得影响医学逻辑 |

患者 UI 中硬编码领域语义包括：前端自行用阈值生成“先把短句说稳/声音偏轻/需要关注”，ECharts 直接画不同 attempt，Profile code→患者标签映射，以及“推荐/画像/综合分”措辞。这些应由 application DTO 提供已通过 comparability 的状态，前端只负责翻译和展示。

### 3.3 治疗师/Admin 页面

| 页面/组件 | 判定 | 原因 |
|---|---|---|
| `TherapistDashboardView.vue` | REWRITE | 当前是试用质控 dashboard，不是 AttentionItem 工作台 |
| `PatientsView.vue` | ADAPT | 患者列表/搜索可复用；默认密集表、状态仍偏旧 |
| `PatientWorkspaceView.vue` | REWRITE shell, ADAPT components | 已有 workspace 雏形，但 tabs 暴露 Clinical Stage/Profile/Policy/Controlled Actions 内部概念 |
| `TherapistProfilesView.vue` | DEPRECATE directly | 965 行 monolith，把训练记录、发音、趋势、推荐、画像、题库混在一页，不值得渐改 |
| `TherapistAssessmentsView.vue` | REWRITE as formal Assessment workspace | 当前标题和主流程是“自动评估复核”，与新版 Assessment 定义冲突 |
| `TherapistScenarioDialogueReviewView.vue` | ADAPT into evidence detail | 逐轮证据/修订高价值，但应嵌入单次训练详情 |
| `SystemStatusView.vue` | MOVE/DEPRECATE from therapist nav | 是 admin/operations，不属于治疗师主流程 |
| Calibration/Governance/PolicyValidation views | INTERNAL, stop product maintenance | 对算法治理有价值，但不属于产品治疗师 IA；当前路由已重定向 |
| `ClinicalStagePanel` | INTERNAL/ADAPT | 保留正式 assessment 能力，不向产品用户暴露该名 |
| `ProfilePanel` | ADAPT | 可作证据/趋势支撑，不作为一等产品 tab |
| `PolicyPanel`、`ControlledActionsPanel` | INTERNAL prototype | 可复用审批审计模式；不能直接当训练方案 UI |
| Admin page | NEW later | 当前没有独立 admin shell；MVP 不优先 |

### 3.4 API client、mock 与状态

- `frontend/src/api/*.ts` 基本都调用真实后端，不存在大型前端 mock dataset。
- 页面有 empty defaults、fallback copy 和硬编码阈值；它们是 presentation fallback，不代表真实数据支持。
- 真正 mock 多发生在后端 provider 默认值。前端不能根据有字段就断言真实测量。
- `AsyncState`、`EmptyState`、`ErrorState`、`LoadingSkeleton`、`StatusBadge`、`ConfirmDialog`、`Timeline`、`AudioPlayback` 等通用组件值得 KEEP/ADAPT。

## 4. Backend inventory

### 4.1 稳定资产（KEEP）

- 用户、角色、JWT、患者档案、治疗师-患者 assignment 与访问校验。
- SQLAlchemy/Alembic/PostgreSQL 基础。
- `FileAsset`、本地 storage、文件所有权检查、训练录音上传。
- ASR provider、local acoustic provider、TTS/VCL/avatar provider 边界。
- `TrainingSession`、`SessionTask`、`Attempt` 的基本关系。
- 多轮场景状态机、turn/audio/transcript/semantic evidence、人工复核。
- `EvaluationRun`、`EvaluationDimensionResult`、review revision、adoption 与 write failure。
- evidence quality gate、错误脱敏、provider provenance。
- 正式 Assessment metadata、临床来源修订、strict comparability。
- pronunciation shadow、人工修订和 inter-rater 数据。
- Profile V2 immutable snapshots/evidence links。
- calibration / validation / governance 作为 INTERNAL 能力。

### 4.2 需要适配或重构

| 模块 | 判定 | 说明 |
|---|---|---|
| `training.TrainingPlan` | NEW formal model + legacy adapter | 当前只是模板集合，无正式计划语义 |
| `TrainingSession` | ADAPT | 加正式 plan version、状态机、summary、formal/extras |
| `SessionTask` | ADAPT to Exercise instance | 需要 immutable content/strategy snapshot |
| `Attempt` | ADAPT | 增 attempt lifecycle、reliability/evidence links；核心可复用 |
| v2 evaluation | ADAPT/DEPRECATE combined result | 四个 metrics 可复用；总分与反馈混合层需退居兼容 |
| AssessmentSession | ADAPT | 锁定正式评估语义，保留 provenance/review；legacy rows 分类 |
| clinical_stage | KEEP INTERNAL + ADAPT to StageReview support | 不是 StageReview 本身 |
| comparability | REFACTOR/EXTEND | formal assessment comparator 可保留；训练/趋势需要统一 contract |
| AbilityProfile | DEPRECATE gradually | Profile V2 取代其证据聚合职责 |
| training recommendation reviews | ADAPT to Recommendation legacy source | 不能等同 TrainingPlan |
| policy/controlled action | KEEP INTERNAL pattern | 可借鉴 decision approval/audit，不直接暴露领域名 |

### 4.3 不存在的独立后端层

- 没有 repository layer。
- 没有正式 RehabilitationGoal。
- 没有版本化正式 TrainingPlan。
- 没有独立 Observation、Recommendation、AttentionItem、StageReview、TherapistDecision、Milestone 表/aggregate。
- 没有统一 Trend Engine；存在多个局部平均/差值/趋势实现。
- 没有患者首页或治疗师工作台 aggregate application API。

## 5. 数据库 inventory

### 5.1 稳定表族

1. Identity/access：`users`、`patient_profiles`、`therapist_patient_assignments`、family bindings。
2. Evidence/storage：`files`、attempt audio link、scenario turns、analysis provenance。
3. Training event：`training_sessions`、`session_tasks`、`attempts`。
4. Canonical evaluation：`evaluation_runs`、`evaluation_dimension_results`、`evaluation_review_revisions`、`evaluation_write_failures`。
5. Formal assessment：`assessment_sessions` 的 instrument/raw/subscale/total/missing/protocol/reviewer metadata。
6. Professional audit：pronunciation revisions、scenario reviews、calibration/reference annotations。

### 5.2 名称相近但语义不同

- `training_plans` ≠ 新版 TrainingPlan；更接近 DailyExercisePool/legacy plan。
- `training_recommendation_reviews` ≠ TrainingPlan/Recommendation 完整对象；它是旧推荐卡+复核。
- `policy_decisions` ≠ TherapistDecision；当前是 shadow policy output。
- `controlled_action_approvals` ≈ 某种 therapist approval，但只操作现有 session focus/difficulty。
- `assessment_sessions` 接近新版 Assessment，但历史 enum 与 optional attempt 允许旧语义。
- `scenario_expression_reviews`/dialogue review ≠ AttentionItem；它们是资源状态。
- `ability_profiles`/profile snapshots ≠ Observation；它们是聚合投影。

### 5.3 plan/version/session 问题

- 现有 `TrainingPlan` 没有 version、effective_from/to、published_by、goal、stage focus、strategy、supersedes。
- `get_or_create_today_plan()` 只取最新 plan，不按日期，因此 plan 可永久复用。
- `TrainingSession.training_plan_id` 提供了旧 plan 关联，是迁移 adapter 的重要锚点。
- `AssessmentSession` 与 `TrainingSession` 是独立表，没有结构混存；但 Assessment enum/fields 保留 post_training/source_attempt 历史，语义仍可被混用。
- 日常过程指标主要在 `AttemptEvaluation`/EvaluationRun；正式量表在 Assessment JSON/clinical-stage run。旧 Assessment compare 把 long-term/process metric name 都纳入，形成逻辑混存风险。
- Observation/Recommendation 当前散落在 `AttemptScore.main_* / suggestion`、AbilityProfile summary/recommendation、TrainingRecommendationReview、PolicyDecision payload 等。
- Therapist review/decision 分散在多个 review/feedback/approval 表，没有统一生命周期。

## 6. API inventory 与新版页面映射

| 新版页面/任务 | 当前可提供 | 缺口 | 推荐 API 方向 |
|---|---|---|---|
| 患者首页 | `/training/today`、recommendation、profile | active formal plan、今日结构/时长、resume、plan update ack、comparability-gated change | 新 `GET /patient/home` aggregate |
| 今日训练 | create/get session、attempt、audio、analyze、dialogue | resume、pause、exercise lifecycle、retries/skips、formal vs extra、session summary | session-oriented commands/queries |
| 我的进展 | process trend、reports、scenario trends、profile v2 | unified comparability、Observation、Milestone、StageReview summary | `GET /patient/progress` aggregate |
| 我的 | agent/consent/user APIs | accessibility/reminders/privacy preferences | patient settings aggregate |
| 治疗师工作台 | patient list + scattered pending counts | AttentionItem types/reasons/priority/resolution | `GET /therapist/workbench` |
| 患者 workspace | records、assessments、profile、policy | active goal/plan, adherence, attention, observations, plan history | `GET /therapist/patients/{id}/workspace` |
| 单次训练详情 | records、attempt eval、audio、scenario/pronunciation/v3 | unified evidence graph + metric status + observation/recommendation | `GET /therapist/training-sessions/{id}` aggregate |
| 训练方案 | task templates + legacy recommendation/policy | formal versioned plan CRUD/publish/activation | plan application API |
| 阶段回顾 | stage report、assessment compare、profile/policy | StageReview aggregate + therapist decision + plan version creation | stage-review commands/queries |

原则：aggregate/application API 不等于为每个页面建表；DTO 可以组合稳定表与新领域对象。

## 7. 专业指标真实支持矩阵

“真实计算”表示代码中存在确定性算法且可在非 mock provider 条件下产生；“可录入”不等于“已计算”。

| 指标 | source | storage | lifecycle | 本次训练 | 正式 assessment | 真实计算 | mock |
|---|---|---|---|---:|---:|---:|---:|
| 接受度 | 治疗师/人工 `AssessmentCreate.metrics` | `AssessmentSession.metrics.acceptance_score`；clinical v3 映射 `acceptability` | assessment review 后可 formal | 否 | 可作为评估记录，但不是已定义量表评分器 | 否，仅录入 | schema 禁止 assessment `mock_ai`；无自动 mock 值 |
| CADL 总分 | 人工录入 | metrics `cadl_score`，也可存 total/subscale raw | formal assessment | 否 | 是（若确有量表 metadata/施测） | 否 | 无自动 mock |
| 错误次数 | ASR 对齐/规则 engine | `AttemptEvaluation.error_count`、analysis JSON、v3 evidence | attempt→session→trend | 是 | 旧 compare 可读，但不应作为量表 | 是，依赖可用 ASR/质量门 | provider mock 路径存在，但正式 analyze 拒绝 mock |
| 声音响度 | local acoustic active speech | `AttemptEvaluation.loudness` dBFS、analysis JSON、v3 voice_state | attempt | 是 | 否，除非另有专业施测 | 是（相对 dBFS，设备未校准） | acoustic mock 有固定样例，正式 analyze 拒绝 |
| 表达完整度 | transcript/reference alignment (`script_accuracy`) | AttemptEvaluation + v3 `content_reproduction` | attempt | 是（跟读） | 否 | 是；不是临床量表 | mock ASR 不可 formal |
| 言语速率 | transcript 字数 / 有效语音时长 | AttemptEvaluation + v3 fluency evidence | attempt | 是 | 否 | 是 | mock acoustic/ASR 不可 formal |
| WAB 可靠度 | 不存在 | 不存在 | 不存在 | 否 | 尚未支持 | 否 | 否 |
| WAB 流利性 | 人工录入 | `wab_fluency` | assessment | 否 | 可录入 | 否 | 无自动 mock |
| WAB 语法 | 人工录入 | `wab_grammar` | assessment | 否 | 可录入 | 否 | 无自动 mock |
| WAB 信息量 | 人工录入 | `wab_information` | assessment | 否 | 可录入 | 否 | 无自动 mock |
| WAB 复述可懂度 | 人工录入 | `wab_repetition_comprehensibility`；clinical v3 manual intelligibility | assessment | 否 | 可录入 | 否 | 无自动 mock |
| WAB 语序 | 人工录入 | `wab_word_order` | assessment | 否 | 可录入 | 否 | 无自动 mock |

补充：系统还定义了 `wab_comprehensibility`，但新版清单没有把它列为独立指标；需产品/临床确认是否保留。没有代码证明任何 WAB/CADL 数据在当前生产数据库中已真实施测；源码只证明可录入和存储。

## 8. Test baseline 与覆盖分类

### 实测

- Backend：208 passed。
- Frontend：6 files、10 tests passed。
- Alembic：一个 head，当前 DB 为 0039。

### 长期保留

- Auth/role/access/file permission。
- ASR/acoustic/TTS/pronunciation provider contracts。
- error redaction/observability。
- process evidence gate、algorithm safety、evaluation v3 append-only/fingerprint/retry。
- clinical-stage formal readiness/comparability。
- scenario dialogue state/evidence/review。
- profile evidence quality、policy shadow/validation/control safety。

### 未来替换/重写

- 旧 route/sidebar 权限预期。
- 旧页面 API contract 测试。
- 旧 combined score/feedback UI。
- 旧 AbilityProfile 和 `today` plan 语义。
- “所有 assessment 都待逐条复核”的页面行为。

### 当前缺测

- 正式 versioned TrainingPlan 与 activation。
- pause/resume/offline/retry 的端到端闭环。
- unified comparability→trend→explanation。
- AttentionItem rule + resolution。
- StageReview→TherapistDecision→new Plan transaction。
- 患者/治疗师新版 aggregate DTO 与页面 E2E。

## 9. 已发现但本阶段不修复的问题

1. `get_or_create_today_plan()` 不按日期，只取最新 plan。
2. 默认 mock 配置与 `analyze_attempt()` 拒绝 mock 的行为，使 README 所述 mock 闭环不再成立。
3. `LLM_FEEDBACK_PROVIDER` 的通用 feedback factory 不会选择真实实现；只有场景 semantics 路径可真实调用。
4. `SPEECH_EVAL_PROVIDER` 不驱动业务，仅 health/config 使用。
5. 患者进展前端按固定阈值自行解释与画趋势，未统一使用 comparability。
6. `AssessmentSession` 写入口当前是正式人工记录，但旧 enum/source fields 与旧 compare 仍允许语义混淆。
7. 患者 training store 无刷新恢复；当前页面不能实现真正 pause/resume。
8. `TrainingResultView` 是最后一题反馈，不是 session 总结。
9. Admin 没有独立信息架构，admin 复用 therapist shell。
10. 工作区存在未提交 migration/model/frontend changes；Phase 1 前应先明确它们的归属和提交基线。
