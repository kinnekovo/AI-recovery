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

# 6. 评分接口

## 请求分析评分

POST

    /api/attempts/{attempt_id}/analyze

返回：

``` json
{
"overall_score":85,
"dimensions":{
"content":88,
"clarity":80,
"fluency":83,
"loudness":78,
"prompt_dependence":90
}
}
```

未来内部替换：

-   ASR
-   声学分析
-   LLM评价

不影响接口。

------------------------------------------------------------------------

# 7. 报告接口

GET

    /api/reports/latest

返回：

``` json
{
"training_count":10,
"average_score":82,
"suggestion":"继续加强自主表达"
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
