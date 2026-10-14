# 言语康复智能体_API接口设计（V2）

## 1. API规范

统一：

-   RESTful API
-   JSON通信
-   JWT认证
-   文件上传使用 multipart/form-data

响应：

``` json
{
"code":0,
"message":"success",
"data":{}
}
```

------------------------------------------------------------------------

# 2. 认证接口

## 注册

POST

    /api/auth/register

## 登录

POST

    /api/auth/login

返回：

``` json
{
"access_token":"xxx",
"user":{
"id":"uuid",
"role":"patient"
}
}
```

## 当前用户

GET

    /api/users/me

------------------------------------------------------------------------

# 3. 智能体接口

## 创建智能体

POST

    /api/agents

请求：

``` json
{
"name":"妈妈",
"relationship":"mother",
"personality_style":"gentle"
}
```

------------------------------------------------------------------------

## 获取智能体列表

GET

    /api/agents

------------------------------------------------------------------------

## 设置当前智能体

PUT

    /api/users/current-agent/{agent_id}

------------------------------------------------------------------------

## 上传头像

POST

    /api/agents/{agent_id}/avatar

------------------------------------------------------------------------

## 上传声音样本

POST

    /api/agents/{agent_id}/voice

参数：

multipart/form-data

字段：

    audio_file

流程：

上传声音

↓

调用声音克隆服务

↓

保存voice_id

------------------------------------------------------------------------

## 生成欢迎语音

POST

    /api/agents/{agent_id}/welcome-audio

返回：

``` json
{
"audio_url":"xxx.wav"
}
```

------------------------------------------------------------------------

# 4. 训练接口

## 获取训练类型

GET

    /api/training/types

返回：

``` json
[
"repeat",
"scenario"
]
```

------------------------------------------------------------------------

## 获取今日训练

GET

    /api/training/today

返回：

``` json
{
"plan_id":"uuid",
"title":"今日训练",
"status":"completed",
"items_count":6,
"recommended_completed":true,
"completed_recommended_sessions":1
}
```

------------------------------------------------------------------------

## 获取训练推荐

GET

    /api/training/recommendation

当前主路径为算法推荐，不需要治疗师逐条审批。推荐由能力画像、趋势归因和自适应策略共同生成。

返回：

``` json
{
"recommended_type":"repeat",
"headline":"练一组连贯短句",
"reason":"最近说话节奏偏慢，可以用熟悉短句练习连续表达。",
"focus_points":["一句话尽量连起来","停顿少一点"],
"suggested_minutes":12,
"content_level":"L2",
"autonomy_level":"S2",
"policy_version":"phase4.3",
"adaptation_note":"近期表现有波动，系统暂时保持当前难度。",
"reminder":"今天保持当前节奏，完成一组就可以。",
"task_sequence":[]
}
```

------------------------------------------------------------------------

## 创建训练会话

POST

    /api/training/session

请求：

``` json
{
"type":"repeat",
"recommendation_source":"system",
"recommendation_headline":"练一组连贯短句",
"recommendation_task_ids":["uuid-1","uuid-2","uuid-3"]
}
```

推荐入口会一次创建任务组中的多个 `session_tasks`。自选训练仍可只传 `type`。

------------------------------------------------------------------------

## 获取训练内容

GET

    /api/training/session/{id}

------------------------------------------------------------------------

# 5. 作答接口

## 创建尝试

POST

    /api/attempts

------------------------------------------------------------------------

## 上传录音

POST

    /api/attempts/{attempt_id}/audio

multipart/form-data：

    audio_file

------------------------------------------------------------------------

## 获取作答状态

GET

    /api/attempts/{attempt_id}

------------------------------------------------------------------------

# 6. 评价接口

## 获取评价指标字典

GET

    /api/evaluations/metrics

可选查询参数：

``` text
category=process
category=long_term_effect
```

返回：

``` json
[
{
"id":"uuid",
"name":"script_accuracy",
"category":"process",
"description":"正确发音字数 / 脚本总字数，用于衡量脚本输出完整性。",
"unit":"%",
"normal_range":{"target":100,"operator":">="}
}
]
```

------------------------------------------------------------------------

## 保存单次作答评价指标

POST

    /api/evaluations/attempts/{attempt_id}

请求：

``` json
{
"items":[
{
"metric_name":"script_accuracy",
"value":95,
"evaluation_source":"human"
}
]
}
```

`evaluation_source` 支持：

- mock_ai
- human
- clinician

返回保存后的指标值列表。该接口用于保留人工评价和未来治疗师评价入口。

------------------------------------------------------------------------

## 获取单次作答评价指标

GET

    /api/evaluations/attempts/{attempt_id}

返回：

``` json
{
"attempt_id":"uuid",
"items":[
{
"metric_name":"script_accuracy",
"metric_category":"process",
"value":95,
"evaluation_source":"human"
}
]
}
```

------------------------------------------------------------------------

## 获取过程性指标趋势

GET

    /api/evaluations/process-trend

可选查询参数：

``` text
limit=20
```

返回最近训练 attempt 的过程性指标趋势，用于患者端 `/evaluation` 折线图。

返回：

``` json
{
"items":[
{
"attempt_id":"uuid",
"created_at":"2026-08-09T10:00:00Z",
"metrics":{
"script_accuracy":95,
"error_count":1,
"speech_rate":150,
"loudness":65
}
}
]
}
```

------------------------------------------------------------------------

## 请求作答分析

POST

    /api/attempts/{attempt_id}/analyze

Phase 2.2 起，该接口在分析完成后会自动向 `attempt_evaluations` 写入 `mock_ai` 来源的过程性监控指标：

- script_accuracy
- error_count
- speech_rate
- loudness

Phase 2.3 起，该接口返回训练反馈结构，不再返回旧的 `overall_score + dimensions`。

返回：

``` json
{
"attempt_id":"uuid",
"process_metrics":{
"script_accuracy":95,
"error_count":2,
"speech_rate":150,
"loudness":65
},
"feedback":[
{
"metric":"speech_rate",
"current_performance":"言语速率约为 150 字/min，低于参考范围。",
"suggestion":"建议增加连续表达训练，先用熟悉短句做稳定输出。"
}
],
"transcript":"这是一次模拟转写结果"
}
```

Phase 4.4 起，内部 provider 可通过环境变量替换，但接口字段和评分口径保持稳定：

``` env
SPEECH_EVAL_PROVIDER=mock
ASR_PROVIDER=mock
ACOUSTIC_PROVIDER=mock
LLM_FEEDBACK_PROVIDER=mock
```

真实服务接入后仍应映射到：

- script_accuracy
- error_count
- speech_rate
- loudness

不影响接口。

------------------------------------------------------------------------

# 7. 报告接口

## 阶段性评估

POST

    /api/assessment

用于保存训练前、训练中或训练后的阶段性评估。WAB、CADL 和接受度数据应来自人工或治疗师录入，不应由模型自动伪造。

请求：

``` json
{
"assessment_type":"baseline",
"evaluation_source":"human",
"metrics":{
"wab_information":6,
"wab_fluency":5,
"wab_grammar":4,
"wab_word_order":4,
"wab_comprehensibility":7,
"wab_repetition_comprehensibility":6,
"cadl_score":68,
"acceptance_score":8
},
"notes":"训练开始前评估"
}
```

返回：

``` json
{
"id":"uuid",
"assessment_type":"baseline",
"evaluation_source":"human",
"assessed_at":"2026-08-09T10:00:00Z",
"metrics":{},
"notes":"训练开始前评估"
}
```

------------------------------------------------------------------------

GET

    /api/assessment/history

可选查询参数：

``` text
assessment_type=baseline
```

返回阶段性评估历史，按评估时间升序排列。

------------------------------------------------------------------------

GET

    /api/assessment/compare

默认比较最早一次和最近一次阶段性评估。

可选查询参数：

``` text
baseline_id=uuid
current_id=uuid
```

返回：

``` json
{
"baseline_assessment":{},
"current_assessment":{},
"metrics":{
"wab_information":{
"baseline":6,
"current":8,
"change":2
}
}
}
```

------------------------------------------------------------------------

GET

    /api/reports/latest

返回：

``` json
{
"training_count":10,
"process_monitoring_summary":{
"avg_correct_script_word_rate":96.5,
"avg_error_count":1.2,
"avg_speech_rate_wpm":175,
"avg_loudness_dba":64
},
"effect_comparison":{
"wab":{},
"cadl":{},
"preference_acceptance":{}
},
"suggestion":"继续加强脚本输出稳定性，并观察阶段性WAB/CADL变化。"
}
```

------------------------------------------------------------------------

# 8. 文件接口

上传：

POST

    /api/files/upload

支持：

-   avatar
-   voice_sample
-   audio
-   generated_audio

------------------------------------------------------------------------

# 9. AI扩展接口

## ASR

POST

    /api/ai/asr

## TTS

POST

    /api/ai/tts

## 声音克隆

POST

    /api/ai/voice-clone

## 能力画像

GET

    /api/profile/ability

------------------------------------------------------------------------

# 10. 三端协作接口

## 治疗师：患者列表

GET

    /api/therapist/patients

## 治疗师：训练记录

GET

    /api/therapist/patients/{patient_user_id}/training-records

## 治疗师：训练趋势

GET

    /api/therapist/patients/{patient_user_id}/training-trends

## 治疗师：当前算法推荐

GET

    /api/therapist/patients/{patient_user_id}/training-recommendation

## 治疗师：推荐效果、趋势归因与提醒

GET

    /api/therapist/patients/{patient_user_id}/training-recommendation/effects

返回包含：

``` text
trend_status
trend_summary
strategy_hint
evidence_points
attribution_points
patient_reminder
family_reminder
therapist_reminder
```

## 治疗师：自然语言调整说明

GET

    /api/therapist/patients/{patient_user_id}/recommendation-note

POST

    /api/therapist/patients/{patient_user_id}/recommendation-note

该接口是治疗师影响推荐的当前主入口。治疗师不审批每条推荐，只补充下一次训练方向。

## 家属：绑定患者列表

GET

    /api/family/patients

## 家属：陪伴观察

GET

    /api/family/observation?patient_user_id=uuid

返回家属可理解的水平、趋势和陪伴提醒，不展示治疗师级专业量表。

------------------------------------------------------------------------

# 11. Deprecated 兼容接口

以下接口保留用于 Phase 3 历史兼容，不再作为推荐主路径。前端主界面不应再依赖这些接口。

## Deprecated：治疗师推荐复核

POST

    /api/therapist/patients/{patient_user_id}/training-recommendation/review

历史用途：治疗师确认或调整系统推荐。

当前替代：`POST /api/therapist/patients/{patient_user_id}/recommendation-note`

## Deprecated：推荐策略反馈

POST

    /api/therapist/patients/{patient_user_id}/training-recommendation/strategy-feedback

历史用途：治疗师记录推荐效果判断。

当前替代：`GET /api/therapist/patients/{patient_user_id}/training-recommendation/effects` 自动返回趋势归因与提醒。

## 治疗师复核闭环（new-UI）

所有写接口均要求治疗师或管理员身份，并校验患者授权范围。证据包保留原音、原始转写和自动评估版本；治疗师修订写入独立审计记录，不覆盖自动结果。待办状态依次使用 `open`、`acknowledged`、`in_review`、`waiting_information`、`waiting_plan_publish` 与关闭状态；“等待方案发布”只在正式方案发布成功后关闭。

### 待复核队列与证据包

- `GET /api/v2/therapist/review-queue`：筛选待办队列；支持 `status`（逗号分隔）、`type`、`priority`、`patient`、`assigned_to`（`me`/`unassigned`/`all`）、`cursor`、`limit`。
- `GET /api/v2/therapist/attention-items/{item_id}/review-bundle`：获取患者目标、当前方案、待办、原音/ASR/对话轮次、自动评估、质量门控、证据、历史修订和审计事件。
- `POST /api/v2/therapist/attention-items/{item_id}/begin-review`：领取/继续复核；已由他人接手时返回 `409`。
- `POST /api/v2/therapist/attention-items/{item_id}/release`：释放尚未开始的接手事项。
- `POST /api/v2/therapist/attention-items/{item_id}/audio-opened`：记录治疗师打开待办关联录音的事件，body 为 `{ "file_id": "uuid" }`。
- `POST /api/v2/therapist/attention-items/{item_id}/wait-for-information`：暂停当前复核，body 为 `{ "reason": "audio_unavailable|source_not_resolved|...", "note": "..." }`。

### 人工评估复核

- `POST /api/v2/therapist/attention-items/{item_id}/evaluation-runs/{run_id}/reviews`：只允许复核属于该待办证据包的运行。body 包含 `review_action`（`confirmed`/`corrected`/`unjudgeable`）、`dimension_result_id`、`revised_value_snapshot`、`evidence_override`、`reason_code`、`reason` 和 UUID `review_request_key`。确认/修正需有患者原音；修正须写明依据。原音缺失时仅能记为无法判断。

### 阶段决定与方案版本

- `POST /api/v2/therapist/attention-items/{item_id}/stage-review`：以明确选择的待办及其证据创建阶段复核；支持 `additional_attention_item_ids`，不能隐式纳入同患者其他待办。
- `GET /api/v2/therapist/stage-reviews/{review_id}`、`POST .../{review_id}/ready`、`POST .../{review_id}/decisions`：读取冻结事实、检查进入决定阶段、保存幂等的治疗师决定。计划调整类决定只创建草稿，并把关联待办转入 `waiting_plan_publish`。
- `GET /api/v2/therapist/training-plans/{plan_id}`、`GET .../{plan_id}/diff`、`PATCH .../{plan_id}`：读取版本上下文与差异、编辑草稿。保存时需携带 `expected_active_plan_id`；基线已变化时返回 `409`。
- `POST /api/v2/therapist/training-plans/{plan_id}/abandon`：废弃草稿；关联来源待办恢复为可复核状态。
- `POST /api/v2/therapist/patients/{patient_user_id}/training-plans/{plan_id}/publish`：body 携带 `expected_active_plan_id` 和幂等 `request_key`。成功后激活新版本、记录发布快照，并原子关闭关联的等待发布待办。
