---
name: academic-talk-organizer
description: Use when a research talk must be organized for a specific audience, goal and time budget, with one claim per slide, evidence strength and prepared Q&A.
---

# 学术汇报内容组织

## 用途与适用条件

面向指定听众、汇报目标与时长，把已有研究材料组织成可讲的页面序列：把“这次汇报要达成什么”转成可检查目标，判断听众先验知识与关注点，按“问题—方法—证据—结论—边界”安排取舍与时间，给每页唯一主张、支撑证据与证据强度，并准备与页面绑定的问答与备用页。

适用条件：`/input/case.json`（或 `--case`）提供研究材料、汇报目标、听众、时长、页数上限或问答要求。典型键：`goal`、`audience`、`duration_min`、`slide_limit`、`sections`、`questions`。

不适用：不生成新的实验结论，不做统计重算，不负责论文精读与图形美化；不伪造幻灯片渲染结果。

## 输入

- `/input/case.json`：主输入。
- `/input/task.md`：存在时补充汇报场合、听众背景与时长。
- 引用的本地文本/JSON 会被实际读取；缺失登记到 `errors`/`uncertainty`。
- 仅标准库；不联网、不写 `/input`。

## 处理流程

1. **读入**：加载 case.json、task.md 与材料，记录来源哈希。
2. **目标转译**：读取显式 goal；缺失时**不编造**，标 `goal_missing`，仅给出基于材料的候选问题。
3. **听众建模**：从 `audience` 与 `audience_level` 判断先验知识（专家/混合/非专业），列出关注点与可能质疑；无输入时标 `audience_missing`。
4. **叙事编排**：按 problem / method / evidence / conclusion / limitation 分节，分配时长与页数；总时长与 `duration_min` 对齐。
5. **页级主张**：每页一句主张，附来源句；同一节内按证据强度排序，弱证据不放到主结论页。
6. **证据强度**：按声明规则判定 strong（统计量/n/CI + 数值）、moderate（有数值无统计）、weak（仅定性）、undeclared（无支撑）；规则写入输出，便于复核。
7. **时间预算**：按中文约 220 字/分钟估算讲述时长，检查单页 <0.5 分钟或总时长偏差 >10%。
8. **问答准备**：读取显式问题；缺失时从局限句与未覆盖要素（对照、样本量、机制）生成问题模板，映射到页面与备用页。
9. **契约落盘**：保留 `case_id` 与全部 `output_contract` 字段。

## 评分维度对应

- **实际效果**：目标可检查、叙事服务听众与时长、每页主张唯一且有证据。
- **完整性**：目标、听众、叙事、页级主张、证据强度、问答六类要素齐备。
- **可核验性**：目标/听众/主张均有输入依据或明确缺失标记。
- **创新增益**：目标—时长—页数联动、证据强度规则化、问答与页面绑定。
- **可靠体验**：缺目标/听众、时长冲突、无证据时显式降级。

## 输出契约

`/app/output/result.json` 顶层保留 `case_id`、`output_contract` 全部字段、`status`、`result`、`evidence`、`uncertainty`、`errors`、`stats`、`skill`、`challenge_id`、`contract_notes`。未支持字段写 `null`，键与原因集中记入 `contract_extras`，便于区分“没产出”与“字段名未知”。

主要交付段：`result.talk_plan.objectives`、`result.talk_plan.audience_model`、`result.talk_plan.narrative`、`result.talk_plan.slides`、`result.qa_prep`。

## 异常处理

| 情况 | 处理 | 输出表现 |
|---|---|---|
| case.json 缺失/非法 | 结构化失败 | 退出码 `2`，`status=insufficient_input`/`failed` |
| 无目标 | 不编造目标 | `objective=null` + `goal_missing` |
| 无听众信息 | 不猜测听众 | `audience_missing`，用中性假设并标注 |
| 材料不足两节 | 不硬凑叙事 | `status=partial`，列缺失角色 |
| 时长与页数冲突 | 保留内容，压缩页数并记录 | `duration_slide_mismatch` |
| 证据强度无法判定 | 标 `undeclared` | 不写“显著” |
| 问答无显式问题 | 生成模板并注明来源 | `derived_from_limitation` |
| 渲染工具缺失 | 仍须生成 pptx；无法渲染时在 deliverable 明确标注 | `deliverable.rendered=false`、`pptx_not_generated` |

## 限制

听众建模与证据强度基于规则而非语义理解；时长估算为经验值，需按实际语速复核。脚本在**同一次运行**内产出汇报结构与全部交付文件，不依赖第二个 Agent 回合。

## 最小调用示例（示例，非官方案例结果）

```bash
python scripts/run_skill.py --case /input/case.json --out /app/output/result.json
```

示例输入（示意）：`goal` 为“让评审认可方法新颖性”，`audience` 为“评审专家”，`duration_min=15`，三节材料。示例输出（示意）：`status="success"`，narrative 五节、slides 每页一个 claim、qa_prep 含局限类问题。仅为示例，不代表官方固定案例结果。


## 最终交付物（本次运行直接生成）

一次运行同时落盘结构与成品，路径均在 `--out` 同级目录：

1. `result.json` —— 契约齐全的结构化结果（目标、听众、叙事、页级主张、证据强度、时间预算、问答、检查项）。
2. `deck.pptx` —— 真实可编辑演示文件（OOXML），页标题 = 叙事角色 + 该页主张，文字与备注均可编辑。
3. `slides/slide-NN.svg` + `slides/slide-NN.png` —— 逐页矢量源与真实位图预览。
4. `speaker-notes.md` —— 与页面文字物理分离的讲稿。
5. `slide-evidence-map.json`、`slide-export-checks.json` —— 页级证据映射与导出前检查记录。
6. `result.deliverable` 记录各产物路径、页数、字节数与渲染结果。

工具确实缺失时如实降级：`deliverable.rendered=false` 并在 `uncertainty` 写明原因，不声称已渲染。

## Quickstart

在包根目录执行：

```bash
python scripts/run_skill.py --case examples/demo-case/case.json --out ./demo-output/result.json
```

- 演示案例：`examples/demo-case/case.json`（15 分钟报告材料：问题/方法/结果/结论/局限五节，含 2 个预设问答；纯合成）。
- 输出：`result.json` 含 `talk_plan`、`slides`（页级 claim 与证据映射）、`qa_prep`、`narrative`、`audience_model`，同目录下 `deck.pptx`、`slides/*.svg|.png`、`speaker-notes.md`、`slide-evidence-map.json`、`slide-export-checks.json` 同一次运行写出；本案例实测 `status="success"`、8 页、双跑逐字节一致。

## 交付保证与评分对齐

调用顺序（固定，两条命令等价，第二条可选）：

1. 运行包内脚本：`python scripts/run_skill.py`（默认读 `/input/case.json`，写 `/app/output/result.json`）；路径不同时用 `--case` / `--out` 指定。本次运行即产出 `result.json` 与全部交付文件（`deck.pptx`、`slides/*`、讲稿、证据映射、导出检查）。
2. 自检：`case_id` 与输入一致；`output_contract` 每个字段都存在；`status` 为 `success`（仅在确实缺输入时为 `partial`）；无 `pending` 占位；数字、引用、来源可逐条回溯。

运行保证：

- 输入缺失、JSON 损坏、字段异常、输出目录不存在时，仍须写出结构化 `result.json` 并正常结束，不得崩溃或非零退出。
- 不联网、不伪造数据、不声称平台评分或官方案例结果。
- 交付物必须是可直接编辑与复核的成品，而不是流程说明。

评分对齐（本题五个维度）：

- 实际效果（40）：完整产出任务要求的最终成品，覆盖全部输入条目，可直接进入修改流程。
- 使用增益（25）：体现相对基础 Agent 的可验证改进（结构化、术语/数字/引用核对、可编辑性）。
- 创新增益（15）：保留方法学增量（分块、对齐、二次校验、版本比对等），并用结果证明其价值。
- 可靠体验（10）：异常输入有明确降级与说明，不同长度/文体/重复运行下稳定产出。
- 生态贡献（10）：用途、调用、输入输出、限制、示例、维护信息齐全，资源可被他人复用。

## 最终交付强制要求

1. **一次运行交付成品，不是流程说明**：脚本本次运行即在 `result.json` 之外写出 `deck.pptx`、逐页 `slides/*.svg|.png`、`speaker-notes.md`、`slide-evidence-map.json`、`slide-export-checks.json`；`result.json` 内 `talk_plan` / `slides` / `qa_prep` 均带实质内容，不含 `pending`、`TODO` 占位。
2. **必须覆盖全部输入条目**：输入中的每个章节、问题、文献、图、页面、指标都要有对应条目，不得只处理示例或首条；确实缺失的条目写入 `uncertainty` / `limitations` 并说明原因，不得静默跳过。
3. **必须自检后再交付**：`case_id` 与输入一致；`output_contract` 每个字段都存在；状态值取本题契约规定的枚举；数字、单位、引用、来源可逐条回溯；结果内部无自相矛盾。
4. **参数等价**：`python scripts/run_skill.py --case <输入> --out <输出>` 与 `--output <输出>` 等价；默认 `/input/case.json` → `/app/output/result.json`。
5. **平台用 3 个固定案例分别运行**：逻辑要由输入驱动，不针对某一份示例硬编码；字段命名差异走别名匹配与显式降级，并在 `uncertainty` 记录假设。
