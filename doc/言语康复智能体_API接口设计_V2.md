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

------------------------------------------------------------------------

## 创建训练会话

POST

    /api/training/session

请求：

``` json
{
"type":"repeat"
}
```

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

未来内部替换：

-   ASR
-   声学分析
-   规则评价
-   LLM反馈生成

不影响接口。

------------------------------------------------------------------------

# 7. 报告接口

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
