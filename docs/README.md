# 文档导航

本目录是项目文档的唯一主入口。根目录仅保留 `README.md`、`PRODUCT.md` 和 `DESIGN.md` 三份总览文档。

## 分类

- `product/`：PRD、MVP、交互规范、产品路线、试用与授权资料。
- `architecture/`：当前代码库、系统架构、数据库、API 与技术选型。
- `development/`：本地开发、部署、备份恢复和试用数据初始化。
- `algorithms/`：临床依据、评估算法、能力画像、推荐策略和场景对话设计。
- `archive/`：按阶段保存的历史方案、实施报告和重构记录，仅供追溯，不代表当前实现。
- `maintenance/`：代码审计、清理和后续维护记录。

## 推荐阅读顺序

1. [项目 README](../README.md)
2. [代码库指南](architecture/CODEBASE_GUIDE.md)
3. [产品设计](product/Speech_Rehab_Product_Design_v1.md)
4. [UI 与交互规范](product/Speech_Rehab_UI_Interaction_Spec_v1.md)
5. [总体系统架构](architecture/言语康复智能体_总体系统架构设计.md)
6. [生产部署指南](development/言语康复智能体_生产部署指南.md)
7. [安全清理报告](maintenance/CLEANUP_REPORT.md)

## 文档状态约定

- `product/`、`architecture/`、`development/`、`algorithms/`：继续维护的有效资料；实现冲突时以代码、迁移和 API 合约为准。
- `archive/`：历史快照，不应作为新开发的唯一依据。
- 标注 `REVIEW_REQUIRED` 的项目表示暂时无法证明可删除或仍需人工确认，因此被保留。
