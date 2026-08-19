# GitHub 策略源码参考（只读）

这些文件只是参考，正式策略必须写到 `/mnt/agent/workspace/output/main.py`。
禁止把整棵参考树拷进 `output`；禁止在正式策略里写死 `/mnt/agent/workspace`。
正式回放只能 `numpy`/`pandas` + 单文件；用 PIT：`available_at <= inference_at`；默认 `08:30` 只能用 T-1 日线。
财务用公告日/`available_at`，不用 `end_date` 偷看。

## 任务

阅读 `vendor/` 里的策略片段和 `rewrite_notes.md`，改写成自洽的单文件 PIT 策略。
多数仓库没有 license，只作研究参考，**不要整文件贴进 output**。
不要引入 vnpy / qlib / rqalpha / backtrader 产品框架，也不要 `import` 本目录。

## 本包文件

| 文件 | 用途 |
|---|---|
| `sources.md` | 来源排序、URL、收录了什么、失败了什么 |
| `rewrite_notes.md` | 12 条种子如何接到 `generate_orders` |
| `playbook_notes.md` | QuantsPlaybook 未拉取的笔记本：RSRS / ICU / STR / 球队硬币 / 筹码的公开公式 |
| `vendor/` | 稀疏源码，体积刻意压小 |

`vendor/.gitignore` 排除 `.git`、PDF、笔记本。
