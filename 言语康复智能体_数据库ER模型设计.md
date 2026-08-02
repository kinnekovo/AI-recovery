# 言语康复智能体：数据库 ER 模型设计

## 1. 设计目标

数据库设计需要支撑：

- 个性化陪伴智能体创建
- 患者言语训练流程
- 多次尝试记录
- 语音分析与评分
- 能力画像更新
- 家属查看报告
- 后续 AI 能力扩展

核心原则：

1. 患者、智能体、训练记录相互独立。
2. 每次训练尝试均可追溯。
3. 评分结果必须能够追溯到原始录音和分析结果。
4. 智能体只负责陪伴身份，不保存患者能力。
5. AI 服务结果与业务数据分离。

---

# 2. 核心实体

## 用户与身份

- users
- patient_profiles
- family_patient_links

## 智能体与授权

- agents
- consents
- files

## 训练题库

- task_templates
- task_prompts
- scoring_configs

## 训练过程

- training_plans
- training_plan_items
- training_sessions
- session_tasks
- attempts

## 分析与评分

- analysis_jobs
- attempt_analysis_results
- attempt_scores

## 能力画像与报告

- ability_profiles
- ability_profile_snapshots
- training_reports

---

# 3. 核心关系

```
User
 |
 | 1:1
 |
PatientProfile
 |
 | 1:N
 |
Agent


PatientProfile
 |
 | 1:N
 |
TrainingPlan
 |
 | 1:N
 |
TrainingPlanItem


PatientProfile
 |
 | 1:N
 |
TrainingSession
 |
 | 1:N
 |
SessionTask
 |
 | 1:N
 |
Attempt
 |
 | 1:1
 |
AttemptScore
```

---

# 4. 关键表说明

## users

保存所有账号。

主要字段：

- id
- username
- password_hash
- role
- status
- created_at

角色：

- patient
- family
- admin
- therapist（未来）

---

## patient_profiles

保存患者特有信息。

主要字段：

- user_id
- current_agent_id
- onboarding_status
- assessment_status
- training_status

患者能力属于患者，而不是智能体。

---

## agents

保存陪伴智能体。

主要字段：

- patient_profile_id
- name
- relationship
- avatar_file_id
- voice_sample_file_id
- voice_external_id
- personality_style
- generation_status

支持：

- 多智能体
- 默认绑定一个当前智能体
- 后续切换

---

## consents

保存声音和形象授权。

主要字段：

- user_id
- agent_id
- consent_type
- consent_version
- consent_status
- consented_at
- revoked_at

---

## files

统一管理：

- 头像
- 声音样本
- 患者录音
- TTS生成音频

数据库只保存文件元数据。

---

# 5. 训练模型

## task_templates

训练题模板。

包含：

- 任务类型
- 内容难度 L1-L5
- 自主阶段 S1-S4
- 目标文本
- 评分配置


## task_prompts

保存多级提示：

无提示

↓

语义提示

↓

关键词提示

↓

句式提示

↓

完整示范


## training_plans

系统安排的训练计划。


## training_sessions

患者实际进行的一次训练。


## attempts

一次具体作答。

支持：

- 多次重试
- 不同提示等级
- 不同录音结果

---

# 6. 评分模型

## attempt_analysis_results

保存原始分析结果：

- ASR文本
- 声学指标
- 语义指标
- 模型输出


## attempt_scores

保存最终评分：

- 综合分
- 内容表达
- 清晰度
- 流畅度
- 音量
- 提示依赖
- 改进建议


分析结果和评分结果分离，方便未来重新评分。

---

# 7. 能力画像

## ability_profiles

保存当前能力。

包括：

- 内容表达
- 清晰度
- 流畅度
- 音量
- 提示依赖
- 当前训练等级


## ability_profile_snapshots

保存历史版本。

用于：

- 趋势分析
- 家属报告
- 算法优化

---

# 8. MVP开发优先数据库

第一阶段优先实现：

1. users
2. patient_profiles
3. agents
4. files
5. task_templates
6. training_sessions
7. attempts
8. attempt_scores

后续增加：

- consent
- family_patient_links
- ability snapshots
- reports

---

# 9. 关键设计原则

1. 不把训练数据绑定到智能体。
2. 不只保存最终一次成绩。
3. 不把大文件存入数据库。
4. AI分析结果需要版本化。
5. 数据库设计支持未来模型替换。
