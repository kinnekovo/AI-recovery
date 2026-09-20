# Product Reset 渐进式重构计划

> 本文是 Phase 0 的规划产物，不代表已经开始编码。实施时以 `docs/product/Speech_Rehab_Product_Design_v1.md` 与 `docs/product/Speech_Rehab_UI_Interaction_Spec_v1.md` 为唯一产品上游；当前仓库尚未建立 `docs/product/`，开始 Phase 1 前应先确认并纳入这两份已审阅规格。

## 1. 实施原则与阶段依赖

实施采用 additive-first 与 strangler pattern：先在旧系统旁建立新版领域和页面入口，通过 application/facade API 复用稳定底层能力；新版闭环稳定后，旧页面和旧 API 才进入冻结与退役流程。任何阶段都不删除历史表、历史数据或仍被旧页面使用的 API。

```mermaid
flowchart LR
    P0[Phase 0<br/>审计与映射] --> P1[Phase 1<br/>首个患者垂直切片]
    P1 --> P2[Phase 2<br/>训练生命周期完善]
    P2 --> P3[Phase 3<br/>证据、指标与趋势]
    P3 --> P4[Phase 4<br/>治疗师工作台]
    P4 --> P5[Phase 5<br/>阶段复核与决策闭环]
    P5 --> P6[Phase 6<br/>正式评估对齐]
    P6 --> P7[Phase 7<br/>切换与旧模块冻结]
```

跨阶段约束：

- 每个数据库变更只新增表、列、索引或兼容关系；删除与破坏性改名不属于本计划前半程。
- 旧 API 保持可运行；新版页面调用新的 application API，不直接绑定数据库表形状。
- ASR、acoustic、LLM、音频存储和现有 evaluation provider 不因页面重做而替换。
- 每个阶段必须在独立部署后仍可运行，并保留回滚到旧路由/旧页面的开关。
- 每个阶段都先定义验收数据和自动化测试，再允许扩大范围。
- 未形成患者—训练—进展—治疗师决策闭环前，不投入管理员重做、复杂报表或无关底层抽象。

## 2. Phase 0：审计与方案确认（当前阶段）

### Goal

建立真实代码库地图、现状基线、新旧概念映射、目标架构和可执行阶段计划；不修改产品行为。

### Scope

- 完整阅读两份新版规格。
- 审计前后端、模型、迁移、API、provider、测试与主要调用链。
- 核实专业指标的数据来源与真实性。
- 记录问题，不修复问题。

### Files/modules likely affected

仅新增 `docs/refactor/00_codebase_guide.md` 至 `docs/refactor/04_refactor_plan.md`。业务目录不应产生 Phase 0 变更。

### Database impact

无。只读检查迁移历史、当前 head 和模型关系。

### API impact

无。

### Frontend impact

无。

### Tests

- Backend baseline：`python -m pytest`，实际结果 `208 passed in 6.44s`。
- Frontend baseline：`npm test -- --run`，实际结果 `6 passed test files / 10 passed tests`，耗时 `21.58s`。
- Alembic：单一 head `0039_controlled_governance`，当前数据库亦位于该 revision。

### Acceptance criteria

- 五份文档覆盖用户要求的全部审计问题。
- 所有关键结论均能追溯到真实文件、类、函数、表或测试。
- 不把手工输入、mock 或仅有字段定义的指标写成“已真实计算”。
- 除分析文档外没有本阶段产生的仓库改动。

### Rollback strategy

文档变更可独立撤回，不影响运行系统或数据。

## 3. Phase 1：首个患者垂直切片——真实 TrainingPlan 驱动

### Goal

用最小范围打通新版产品第一条真实闭环：

`患者首页 → 今日训练 → 单题 Exercise/Attempt → Session 总结 → 我的进展最小版本`

这条链必须由正式、可版本化的新版 `TrainingPlan` 驱动，而不是继续把旧 `training_plans` 当成新版计划。

### Scope

- 新增 `RehabilitationGoal` 与正式、版本化 `TrainingPlan`/plan version 模型。
- 为旧 `training.TrainingPlan` 建立只读或迁移期 adapter，不原地改变其语义。
- 新版计划 v1 只需支持一个患者、一项目标、一个有效版本、一项 repeat Exercise。
- 复用现有 `TrainingSession`、`SessionTask`、`Attempt`、音频、ASR、acoustic 和 evaluation pipeline；以新增关联和 application service 串联。
- 新增患者首页、今日训练、单题训练、Session 总结、最小进展所需的 aggregate API。
- 新旧患者路由短期并存，由 feature flag 或独立 `/v2` 路由选择。

### Files/modules likely affected

- Backend：`backend/app/models/`、`backend/app/schemas/`、`backend/app/modules/training/`、`backend/app/modules/evaluation/`、`backend/app/routers/` 或新增 `backend/app/application/`。
- Database：`backend/migrations/versions/` 新增 additive migration。
- Frontend：`frontend/src/router/`、`frontend/src/views/patient/`、`frontend/src/components/training/`、`frontend/src/api/`、`frontend/src/stores/`。
- Tests：新增模型、application API、兼容性和患者垂直切片测试；不改写旧测试语义来迁就新实现。

### Database impact

- 新增目标表和正式 plan/version 表；建议用独立主键及 `version_number`、`status`、`effective_from/to`、`created_by`、`supersedes_id` 等审计字段。
- 为 `training_sessions` 增加可空的新计划版本外键，保留现有 `training_plan_id`。
- 如需练习快照，新增 plan exercise/item 表；不覆盖 `task_templates` 或历史 `session_tasks`。
- 所有新列先可空或有安全默认值，不回填破坏性数据，不删除旧列。

### API impact

建议首先提供面向页面的 application API，而非每表一套 CRUD：

- `GET /api/v2/patient/home`：当前目标、有效计划、今日任务、最近进展摘要。
- `POST /api/v2/training/sessions`：按有效计划创建/恢复今日 Session。
- `POST /api/v2/training/sessions/{id}/attempts` 或兼容现有上传/分析分步协议。
- `POST /api/v2/training/sessions/{id}/complete`。
- `GET /api/v2/training/sessions/{id}/summary`。
- `GET /api/v2/patient/progress?window=...`：最小、事实型指标摘要。

旧 endpoint 不删除；adapter 把现有 attempt/evaluation 结果转换为 v2 DTO。

### Frontend impact

- 建立新版患者 shell 的最小路由和导航；只呈现规格要求的核心入口。
- 首页不直接拼多个旧 endpoint，由 `/patient/home` aggregate 返回页面模型。
- 训练进度改由服务端 Session/Exercise 状态驱动，不再仅依赖组件内 `currentTaskIndex`。
- Session 总结从持久化数据读取，不依赖 Pinia 中最后一次反馈。
- “我的进展”第一版只展示一个有真实来源且可解释的指标，例如相同任务上下文中的表达完整度或言语速率趋势。

### Tests

- 新模型约束、plan version 不可变性/生效规则测试。
- application service：没有有效计划、有一个有效计划、重复创建今日 Session、Session 完成等测试。
- 现有 provider contract 与失败处理回归测试。
- API contract 测试及鉴权/患者隔离测试。
- 前端路由、首页状态、单题 Attempt、刷新恢复、总结页组件测试。
- 至少一个端到端 happy path；mock provider 必须明确标注为非正式结果，不能冒充真实临床指标。

### Acceptance criteria

- 一个测试患者能够通过正式 TrainingPlan v1 完成完整路径，刷新页面后 Session 状态仍正确。
- Attempt 使用现有音频、ASR、acoustic 与 evaluation 能力并产生可追溯 Evidence/Metric DTO。
- Session 总结来自数据库，进展指标有明确 source、context 和 comparability 状态。
- 没有有效计划时显示安全空态，不临时生成无限期“今日计划”。
- 旧患者页面和全部旧测试仍能运行。

### Rollback strategy

- 关闭 v2 patient feature flag/撤回新版路由即可回到旧页面。
- 新表和新可空列保留但停止写入；不做 down migration 删除数据。
- application API 可停止暴露，旧 API/provider 路径不受影响。

## 4. Phase 2：训练生命周期与患者体验完善

### Goal

把 Phase 1 的单题切片扩展为可实际使用的每日计划执行体验，同时仍不引入治疗师复杂工作台。

### Scope

- 一个计划包含多项 Exercise，并区分正式计划内容与额外练习。
- Session 支持开始、暂停、恢复、跳过、完成和中止；异常退出可恢复。
- 引入 Exercise 类型适配层，先接 repeat，再接现有 scenario dialogue。
- 支持提示级别、难度快照、帮助请求和患者可理解的反馈层级。
- 完成患者端设置/授权边界所必需的最小能力；不优先扩展管理员功能。

### Files/modules likely affected

- `backend/app/modules/training/`、`backend/app/modules/scenario_dialogue/`、相关 models/schemas/routers。
- `frontend/src/views/patient/`、`frontend/src/components/training/`、training store/API client。
- 新增生命周期迁移与状态机测试。

### Database impact

- additive 增加 Session/Exercise 状态、顺序、formal/extra、暂停时间、完成原因、提示与帮助事件等字段或事件表。
- 保留旧 `SessionTask` 和 scenario 表；用映射关系接入，不批量改写历史记录。

### API impact

- 扩展 session command API：pause/resume/skip/complete/request-help。
- 新增当前 Session 读模型，统一 repeat/scenario 的公共状态，同时允许类型专属 payload。
- 保持旧 scenario endpoint 可用。

### Frontend impact

- 建立服务端状态驱动的多题流程、暂停恢复和明确错误态。
- 用同一训练容器承载 repeat 与 scenario，但不强行抹平两者的交互差异。
- 清晰区分“计划内训练”和“额外练习”。

### Tests

- 状态转换、幂等命令、并发重复提交、权限隔离测试。
- repeat/scenario adapter contract 测试。
- 音频上传失败、provider 不可用、评估拒绝、恢复会话等前端/后端测试。
- 全量旧测试继续作为回归门禁。

### Acceptance criteria

- 多题 Session 可在刷新、断网重试和暂停后恢复，不重复计入 Attempt。
- 两类 Exercise 的公共状态一致，专属评估仍保留原始证据与 provider provenance。
- 患者始终能区分未完成、已完成、不可评分和系统失败。

### Rollback strategy

- 通过 exercise-type 和 lifecycle feature flags 回退到 Phase 1 单题模式。
- 新状态事件保留；旧 Session 路径继续读旧字段。

## 5. Phase 3：Evidence、Metric、Observation、Recommendation 与趋势链

### Goal

建立新版数据语义边界和统一读模型，使患者进展与后续治疗师决策不再直接依赖混合 JSON 或 `AttemptScore`。

### Scope

- 建立 canonical `Evidence`、`Metric` 存储/投影或明确的 append-only 记录层。
- 建立独立 `Observation` 和 `Recommendation`，二者必须引用支持它们的 Evidence/Metric。
- 将现有 attempt analysis、AttemptEvaluation、EvaluationRun、scenario turn、pronunciation 数据通过 adapter 映射进入统一读模型。
- 抽取统一 Comparability Engine，建立确定性 Trend Engine，再把趋势交给 LLM Explanation。
- 产生最小 Milestone 能力；只基于已定义且可比较的规则。

### Files/modules likely affected

- `backend/app/modules/evaluation/`、`assessment/comparability.py`、`clinical_stage/`、scenario/pronunciation modules。
- 新增 application/query 服务和 v2 progress API。
- `frontend/src/views/patient/` 中进展页与 Session 总结。

### Database impact

- additive 新增 evidence/metric/observation/recommendation/milestone 表，或先用不可变投影表承接；保留所有旧结果表。
- 每条事实记录保存 source type/id、算法/provider/version、context、unit、quality status、created_at。
- 不把历史混合 JSON 静默转换成“临床正式指标”；无法证明来源的内容标记 unknown/legacy。

### API impact

- 进展与 Session summary API 返回分区结构：facts/metrics、observations、recommendations。
- 新增趋势查询，响应包含 comparability verdict/reasons，不只返回数值差。
- LLM 只消费已验证的事实/趋势 DTO；输出存为 explanation 或 recommendation，不写回 metric。

### Frontend impact

- “我的进展”按时间窗、可比性和数据质量展示；不可比时解释原因。
- UI 文案和组件视觉上区分事实、系统观察、建议。
- 逐步停止读取旧 `AttemptScore.feedback` 和 AbilityProfile 混合摘要作为权威数据。

### Tests

- 每种 legacy source 的 adapter golden tests。
- 单位、上下文、版本、缺失值、设备/环境条件的 comparability tests。
- Trend Engine 的纯函数测试与 no-comparable-data 测试。
- LLM 输入脱敏/边界与“不得创造事实”测试。
- 数据血缘和重复投影幂等测试。

### Acceptance criteria

- 任一展示指标都可追溯到 Evidence 和产生它的 provider/算法版本。
- Observation 和 Recommendation 不再与 Metric 共存在同一无类型 blob 中。
- 不可比数据不会生成伪趋势；LLM 不决定可比性和数值事实。
- 现有 formal assessment comparability 规则得到保留并可扩展到训练指标上下文。

### Rollback strategy

- v2 query layer 可回退为读取 legacy adapter，不停止原表写入。
- 新投影表可保留重建；关闭趋势/LLM explanation feature flag 不影响训练记录。

## 6. Phase 4：治疗师工作台与 AttentionItem

### Goal

用“需要关注的事项”替换旧的全量记录复核首页，使治疗师可以从异常或到期事项进入患者上下文并采取动作。

### Scope

- 新增 `AttentionItem`，来源包括患者求助、连续失败、不可评分、evaluation shadow-write failure、评估到期、阶段复核到期等。
- 建立新版治疗师工作台 aggregate API。
- 建立患者详情的概览、计划、训练记录、评估和阶段复核入口；内部 policy/controlled-action 页面不再作为产品主导航。
- 复用现有 therapist assignment、scenario review、pronunciation review 和 failure audit 能力。

### Files/modules likely affected

- Backend therapist/application modules、failure/query services、assignment authorization。
- Frontend therapist layout、dashboard、patient workspace、attention list/detail components。
- 旧 `TherapistProfilesView.vue` 进入冻结，只修严重缺陷，不继续加功能。

### Database impact

- additive 新增 attention item 表及 source reference、priority、status、assignee、due_at、resolved_at。
- 对可计算来源可先使用 projection/job 生成；不删除原始 review/failure 表。

### API impact

- `GET /api/v2/therapist/workbench`：计数、优先队列、今日事项。
- `GET /api/v2/attention-items`、`GET /{id}`、acknowledge/resolve 等命令。
- `GET /api/v2/therapist/patients/{id}`：患者详情 aggregate。
- 旧 review API 作为底层 command 被 adapter 调用。

### Frontend impact

- 工作台围绕 AttentionItem，而不是试验统计和所有评估记录。
- 患者详情减少内部实现标签，突出目标、有效计划、近期训练、正式评估和阶段复核。
- review 入口从具体 AttentionItem 上下文进入。

### Tests

- Attention 来源映射、去重、优先级、权限、状态机测试。
- 治疗师只能看已分配患者的隔离测试。
- 工作台空态/错误态/大量事项分页测试。
- scenario/pronunciation 原有 review 回归测试。

### Acceptance criteria

- 治疗师可从一个真实异常或求助事项进入患者记录并完成处理。
- 相同 source 不重复制造未关闭事项，处理结果可审计。
- 工作台不依赖前端汇总多个全量列表。
- 旧治疗师页面仍可通过兼容路由访问，但不再承接新需求。

### Rollback strategy

- 切回旧 therapist layout/dashboard；AttentionItem 生成器暂停，新表保留。
- 原 review endpoint 和原始数据不变。

## 7. Phase 5：StageReview → TherapistDecision → 新计划闭环

### Goal

把阶段性事实、趋势和治疗师判断组织成可审计闭环，并生成新的计划版本，而不是直接修改正在执行的计划。

### Scope

- 新增 `StageReview` 与 `TherapistDecision`。
- 将 `clinical_stage` 保留为内部事实/计算能力，通过 adapter 为 StageReview 提供证据和候选阶段，不把其输出直接当治疗师结论。
- 支持继续、调整目标、调整强度/难度、创建新计划版本、请求正式 Assessment 等决策。
- 决策产生新 TrainingPlan version，旧版本永久保留。
- ControlledAction 的审批/审计模式可复用，但其 session-level action 不等于 TherapistDecision。

### Files/modules likely affected

- `backend/app/modules/clinical_stage/`、controlled/governance audit 相关模块、training plan application service。
- 新的 stage review/decision models、schemas、routers。
- 治疗师患者详情和复核 UI。

### Database impact

- additive 新增 stage_reviews、therapist_decisions 及证据链接。
- plan version 表增加 decision/source relationship；旧计划版本只变更生命周期状态，不覆盖内容。
- clinical_stage v3 和 failure 记录保留。

### API impact

- 创建/读取 StageReview draft、确认 facts、提交 TherapistDecision。
- “创建新计划版本”作为事务性 application command；返回新旧版本关系。
- API 明确区分自动 observation/recommendation 与治疗师正式 decision。

### Frontend impact

- 阶段复核呈现 Evidence/Metric/Trend、系统 Observation/Recommendation 和治疗师表单三层。
- 决策确认页明确其对计划版本的影响。
- 计划变更历史可查看但不可原地编辑历史版本。

### Tests

- clinical_stage adapter、StageReview 状态机、证据完整性测试。
- TherapistDecision 权限、审计、幂等、事务回滚测试。
- 新 plan version 生成及旧版本不可变测试。
- `evaluation_write_failures` 场景和补偿处理测试。

### Acceptance criteria

- 一次阶段复核能从可追溯事实开始，经治疗师决策生成新计划版本。
- 系统建议不能自动成为正式决策。
- clinical_stage 写入失败不会破坏 Assessment 主事务，且可形成可见的 AttentionItem。
- 任何时点均能还原“谁基于什么事实做了什么决定”。

### Rollback strategy

- 禁用新 decision command 和 stage-review UI；继续运行旧 assessment/review 流程。
- 已产生的计划版本和审计数据保留，恢复上一有效版本只通过新增决策/状态变更完成，不删除历史。

## 8. Phase 6：正式 Assessment 对齐与专业指标治理

### Goal

把正式量表施测从日常训练评价中彻底分离，并建立专业指标的来源、质量、审核和可比性规则。

### Scope

- 将现有 `AssessmentSession` 收敛为正式 Assessment application boundary。
- 明确 instrument/version/locale/unit/admin mode/deviation/missing data 的必填或验证规则。
- 对 CADL、接受度和 WAB 各指标逐项决定：手工录入、外部系统导入、经验证的计算器，或暂不支持。
- 移除新 UI 中的“自动评估复核”泛化叙事；Assessment 只表示专业评估。
- 将 formal assessment 指标接入 StageReview，但不混入单次训练 Metric。

### Files/modules likely affected

- `backend/app/modules/assessment/`、assessment schemas/routers、comparability、clinical_stage adapter。
- 新版 therapist assessment UI 和患者详情评估 tab。
- 数据字典、验证规则和相应测试。

### Database impact

- additive 增加数据来源、录入者/审核者、instrument schema version、验证状态等必要字段。
- `source_attempt_id` 等历史兼容字段保留但不作为新建正式 Assessment 的默认语义。
- 不把已有手工指标回填为“自动计算”；不删除历史 `post_training` 数据，按 legacy 分类。

### API impact

- 正式 Assessment create/review/finalize API 使用明确 instrument-specific schema 或验证层。
- 比较 API 只能比较通过 comparability verdict 的正式数据，并返回不兼容原因。
- 导入与手工录入必须携带 provenance。

### Frontend impact

- 正式施测/录入界面展示量表版本、单位、缺失项、偏差、审核状态。
- WAB 可靠度在没有定义来源与算法前不展示为可用指标。
- 患者训练总结不使用 Assessment 命名。

### Tests

- instrument-specific validation、单位、缺失值、版本兼容、审核权限测试。
- CADL/WAB/接受度 provenance 测试。
- legacy assessment 读取兼容测试。
- formal assessment 与 training metric 不混存/不串 API 的边界测试。

### Acceptance criteria

- 每个正式指标都能说明 source、storage、lifecycle、是否计算、是否审核。
- 日常 TrainingSession 不再创建或命名为 AssessmentSession。
- 不存在可靠来源的指标被明确标为 unsupported，而不是显示假数据。
- 旧 Assessment 历史仍可读取和审计。

### Rollback strategy

- 保留旧 assessment API 为 compatibility layer；关闭新录入/审核 UI。
- 新验证状态和 provenance 数据保留，不逆向删除。

## 9. Phase 7：产品切换、旧模块冻结与兼容层收敛

### Goal

在新版完整闭环通过真实使用验证后，将主导航和默认路由切换到新版，并对旧模块建立明确冻结/退役策略；此阶段仍不默认执行破坏性删除。

### Scope

- 新患者/治疗师页面成为默认入口。
- 冻结旧重叠页面和旧 UI 驱动领域模型，不再承接新功能。
- 统计旧 API/页面真实调用，制定后续独立的删除提案。
- 管理员只做支持新版运行所必需的最小调整；复杂报表另立需求。

### Files/modules likely affected

- Frontend router/layout/navigation、legacy views。
- Backend compatibility routers/adapters、API deprecation headers/telemetry。
- 运维文档、数据迁移运行手册和回归测试。

### Database impact

- 默认无 destructive migration。
- 可做经验证的增量 backfill/索引优化；任何删除表/列必须成为后续单独审批阶段，并先有备份、使用证据和恢复演练。

### API impact

- 新 application API 成为默认。
- 旧 API 标记 deprecated，并记录调用方；不立即移除。
- 只有当调用量归零、兼容期限结束且用户另行批准时，才计划删除。

### Frontend impact

- 新 IA 成为唯一默认导航。
- 旧 `TherapistProfilesView`、旧自动评估复核页、重复的 Evaluation/AbilityProfile/Report、独立智能体主入口和内部治理产品页从导航移除。
- 必要时保留只读 legacy 路由用于历史追溯。

### Tests

- 新版患者和治疗师端端到端回归。
- legacy deep-link 与 compatibility API 测试。
- 数据回填 dry-run、可重复执行和校验报告。
- 性能、权限、审计和故障恢复测试。

### Acceptance criteria

- 新版主链在生产等价环境完成真实患者/治疗师验收。
- 新导航不依赖被标记冻结的旧页面。
- 所有旧模块都有 owner、调用证据、保留期限和后续删除条件。
- 回切旧默认路由经过演练且不丢失新版期间的数据。

### Rollback strategy

- 通过路由/feature flag 恢复旧默认入口。
- 保留兼容 API 和历史表，确保新版写入的数据仍可被审计；必要时以只读方式呈现。
- 不用 destructive down migration 作为常规回滚手段。

## 10. 推荐交付门禁

每个编码 Phase 开始前和结束时都应检查：

1. 产品语义是否仍与两份新版规格一致，而非被旧模型反向塑形。
2. 新增数据是否有 source、version、context、quality、actor 与时间戳。
3. 是否复用了稳定 provider、鉴权、数据库、音频、失败处理和审计能力。
4. 是否保持旧路径可运行，且没有通过修改旧测试掩盖回归。
5. 是否能独立部署、独立关闭，并在关闭后保留完整历史。
6. 是否只完成本阶段闭环需要的工作，没有扩展到管理员、复杂报表或无关平台重构。

## 11. Phase 1 开始前必须由产品/临床负责人决定

以下问题会直接改变数据模型或首个垂直切片的验收口径，不能由旧代码替产品规格作答：

1. **TrainingPlan 版本规则**：谁可以发布计划、何时生效、同一患者能否有多个并行有效计划，以及计划内项目在发布后是否完全不可变。
2. **RehabilitationGoal 最小结构**：Phase 1 是只支持一个自由文本目标，还是必须包含目标类别、临床阶段、目标指标与预计周期。
3. **“今日训练”的生成规则**：按自然日、患者时区、计划频次还是治疗师排程生成；暂停后跨日如何处理。
4. **首个真实进展指标**：建议在“表达完整度（script accuracy）”和“言语速率”中选一个，并定义可比上下文、最小样本量与患者可见文案。
5. **mock 数据的产品策略**：开发/演示环境是否允许展示 mock 结果；若允许，必须采用何种醒目标识，且不得进入正式趋势或阶段决策。
6. **Session 与 Attempt 完成口径**：不可评分、患者跳过、provider 失败分别是否计入完成率和计划完成状态。
7. **首个切片是否包含 scenario**：建议 Phase 1 只做 repeat，Phase 2 再接 scenario；若产品必须首发场景训练，需要扩大适配和验收范围。
8. **旧页面并存方式**：由 feature flag、角色白名单还是独立 `/v2` 路由控制，以及谁有权在试点期间回切。
9. **临床责任边界**：Phase 1 中系统反馈哪些可直接给患者看，哪些必须经过治疗师审核。
10. **规格入库与变更治理**：确认附件版本作为 `docs/product/` 唯一上游，并约定后续变更的版本号和审批人。

这些决定确认后，才应把 Phase 1 拆为具体开发任务。本阶段在此停止，不进入实现。
