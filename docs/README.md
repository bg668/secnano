# 文档导航

## 1. 这份 README 的作用

本目录的文档已收敛为"模块边界清单 + 里程碑 + 项目进展"三类核心文档，并在 `architecture-v2` 分支上新增了 V2 架构设计系列文档。

如果你只想快速理解项目当前的正式结论和阅读顺序，从这里开始即可。

## 2. V2 架构文档（`architecture-v2` 分支）

| 文档 | 中文版 | 说明 |
|------|--------|------|
| [architecture_v2.md](./architecture_v2.md) | [architecture_v2_zh.md](./architecture_v2_zh.md) | V2 架构设计参考（模块定义、设计原则、朝廷隐喻） |
| [module_mapping_v2.md](./module_mapping_v2.md) | [module_mapping_v2_zh.md](./module_mapping_v2_zh.md) | 当前模块到 V2 模块的映射与操作分类 |
| [migration_plan_v2.md](./migration_plan_v2.md) | [migration_plan_v2_zh.md](./migration_plan_v2_zh.md) | V2 分阶段实施路线图（Phase 0–9） |

### V2 文档推荐阅读顺序

1. [architecture_v2_zh.md](./architecture_v2_zh.md)（中文）或 [architecture_v2.md](./architecture_v2.md)（英文）
2. [module_mapping_v2_zh.md](./module_mapping_v2_zh.md)（中文）或 [module_mapping_v2.md](./module_mapping_v2.md)（英文）
3. [migration_plan_v2_zh.md](./migration_plan_v2_zh.md)（中文）或 [migration_plan_v2.md](./migration_plan_v2.md)（英文）

## 3. 历史文档（`main` 分支）

建议按以下顺序阅读：

1. [模块边界清单](./module_boundary_checklist.md)
2. [开发里程碑](./development_milestones.md)
3. [项目进展](./project_progress.md)

## 4. 各文档分工

### [module_boundary_checklist.md](./module_boundary_checklist.md)

当前唯一的架构主文档（`main` 分支）。

适合：

- 模块职责边界
- 各模块输入/输出
- 模块之间的数据流转关系
- 与 `nanobot` / `nanoclaw` / `pyclaw` 的耦合策略
- 建议目录结构

### [development_milestones.md](./development_milestones.md)

开发里程碑文档。

只回答：

- 现在有哪些可执行交付物
- 各里程碑完成到什么程度
- 当前剩余的开发节点是什么

### [project_progress.md](./project_progress.md)

动态进展文档。

只回答：

- 当前已经做到哪里
- 还缺什么
- 当前处在哪个阶段
- 下一步准备做什么

## 5. 使用建议

如果你在做不同类型的工作，可以按下面方式查阅：

- 做 **V2 架构讨论**：看 [architecture_v2_zh.md](./architecture_v2_zh.md)
- 做 **V2 模块映射确认**：看 [module_mapping_v2_zh.md](./module_mapping_v2_zh.md)
- 做 **V2 实施排期**：看 [migration_plan_v2_zh.md](./migration_plan_v2_zh.md)
- 做 **main 架构讨论**：看 [module_boundary_checklist.md](./module_boundary_checklist.md)
- 做 **main 开发排期**：看 [development_milestones.md](./development_milestones.md)
- 查 **当前状态**：看 [project_progress.md](./project_progress.md)

## 6. 维护规则

为了避免文档再次混淆，后续维护时建议遵守：

1. V2 架构边界、依赖方向或模块变化，更新 `architecture_v2.md` 及其中文版 `architecture_v2_zh.md`。
2. V2 模块映射变化，更新 `module_mapping_v2.md` 及其中文版 `module_mapping_v2_zh.md`。
3. V2 实施计划变化，更新 `migration_plan_v2.md` 及其中文版 `migration_plan_v2_zh.md`。
4. main 模块边界、依赖方向或目录结构变化，更新 `module_boundary_checklist.md`。
5. 可执行里程碑变化，更新 `development_milestones.md`。
6. 阶段状态变化，更新 `project_progress.md`。
7. 新增可执行能力时，更新 `history.md`。
