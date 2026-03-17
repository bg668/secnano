# 文档导航

## 1. 这份 README 的作用

本目录的文档已收敛为“模块边界清单 + 里程碑 + 项目进展”三类核心文档。

如果你只想快速理解项目当前的正式结论和阅读顺序，从这里开始即可。

## 2. 推荐阅读顺序

建议按以下顺序阅读：

1. [模块边界清单](/Users/biguncle/project/secnano/docs/module_boundary_checklist.md)
2. [开发里程碑](/Users/biguncle/project/secnano/docs/development_milestones.md)
3. [项目进展](/Users/biguncle/project/secnano/docs/project_progress.md)

## 3. 各文档分工

### [module_boundary_checklist.md](/Users/biguncle/project/secnano/docs/module_boundary_checklist.md)

当前唯一的架构主文档。

适合：

- 模块职责边界
- 各模块输入/输出
- 模块之间的数据流转关系
- 与 `nanobot` / `nanoclaw` / `pyclaw` 的耦合策略
- 建议目录结构

### [development_milestones.md](/Users/biguncle/project/secnano/docs/development_milestones.md)

开发里程碑文档。

只回答：

- 现在有哪些可执行交付物
- 各里程碑完成到什么程度
- 当前剩余的开发节点是什么

### [project_progress.md](/Users/biguncle/project/secnano/docs/project_progress.md)

动态进展文档。

只回答：

- 当前已经做到哪里
- 还缺什么
- 当前处在哪个阶段
- 下一步准备做什么

## 4. 使用建议

如果你在做不同类型的工作，可以按下面方式查阅：

- 做架构讨论：看 [module_boundary_checklist.md](/Users/biguncle/project/secnano/docs/module_boundary_checklist.md)
- 做开发排期：看 [development_milestones.md](/Users/biguncle/project/secnano/docs/development_milestones.md)
- 查当前状态：看 [project_progress.md](/Users/biguncle/project/secnano/docs/project_progress.md)

## 5. 维护规则

为了避免文档再次混淆，后续维护时建议遵守：

1. 模块边界、依赖方向或目录结构变化，更新 `module_boundary_checklist.md`。
2. 可执行里程碑变化，更新 `development_milestones.md`。
3. 阶段状态变化，更新 `project_progress.md`。
4. 新增可执行能力时，更新 `history.md`。
