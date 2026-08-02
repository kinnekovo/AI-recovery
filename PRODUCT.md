# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

第一阶段主用户是脑卒中后言语障碍患者，通常在家庭或康复辅助场景中进行短时、重复的言语训练。家属、管理人员和治疗师是后续扩展用户，MVP 暂不开放对应端。

## Product Purpose

言语康复智能体帮助患者创建一个使用熟悉头像和声音的陪伴智能体，并通过它完成跟读训练、场景表达训练、录音、评分反馈和训练记录保存。MVP 成功标准是跑通注册登录到训练记录的完整闭环。

## Positioning

系统不是普通打分练习工具，而是把“熟悉的人物形象和声音”作为康复陪伴媒介，用情感化陪伴降低患者持续训练门槛。

## Operating Context

第一阶段在 Windows 原生环境开发，不使用 Docker、不拆微服务。前端使用 Vue 3、TypeScript、Vite、Vue Router、Pinia、Axios；后端使用 Python、FastAPI、SQLAlchemy 2.x、Alembic、PostgreSQL。本地文件存储目录为 `storage/agent-images`、`storage/voice-samples`、`storage/training-audio`、`storage/generated-audio`。

## Capabilities and Constraints

第一阶段只实现 patient 注册登录、智能体创建、头像上传、声音样本上传、轻量授权确认、Mock 声音克隆、Mock 欢迎语音、训练会话、作答录音上传、Mock 评分、训练报告。AI 能力必须经由后端 `integrations/` 适配层，前端不得直接调用第三方 AI API。

## Brand Commitments

产品名称为“言语康复智能体”。界面语言应克制、清晰、鼓励，避免制造临床诊断承诺。

## Evidence on Hand

设计依据来自项目根目录七份 Markdown 文档：PRD、技术选型、总体架构设计、数据库 ER 模型、MVP 需求说明、API 接口设计、Codex 开发规范。当前没有真实用户素材、头像、声音样本、临床数据或商业证明。

## Product Principles

先完成可运行闭环，再扩展真实 AI 能力。
核心业务规则放在后端，前端只负责交互。
患者、智能体、训练记录独立建模，作答和评分可追溯。
文件与数据库分离，数据库只保存元数据。
Mock 服务接口必须能被真实供应商替换。

## Accessibility & Inclusion

患者端应适合言语障碍康复场景，界面低认知负担、操作路径短、按钮明确、反馈积极，不以诊断语气呈现评分。
