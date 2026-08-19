# 来源与收录

按「对单文件 A 股策略的可改写程度」排序。收录日期 2026-08-19。
未声明 license 的仓库默认仅供阅读，不要整文件复制进正式产物。

## 已收录

1. **WAYLON/ashare-quant-strategies**  
   https://github.com/WAYLON/ashare-quant-strategies  
   无 license。仓库约 3.3MB。`git clone` 经本地 HTTPS 代理 CONNECT 失败，改用 `codeload` zip。  
   收录：`CATALOG.md`；文章 `003` 多资产动量、`006` 高股息低波动、`043` ETF 动量轮动、`048` 小市值、`077` 基本面小市值、`084` RSRS 动量斜率、`097` 多因子低波动。  
   未收录：其余 100+ 篇、整仓 README 宣传数字、006 的百度网盘附件（含提取码）。

2. **yli188/WorldQuant_alpha101_code**  
   https://github.com/yli188/WorldQuant_alpha101_code  
   收录：`101Alpha_code_1.py`、`101Alpha_code_2.py`。  
   跳过：`101 Formulaic Alphas.pdf`。

3. **IdealAuror/Cheap-Stable-Trending-quant**  
   https://github.com/IdealAuror/Cheap-Stable-Trending-quant  
   Apache-2.0。  
   收录：`results/P5-F2F5F6-40d-final-strategy.py`、`docs/CURRENT-STRATEGY.md`。  
   文档里的 12.5 年收益是**对方聚宽回测**，不是本环境结果。

4. **thisiszhou/CTBZStock**  
   https://github.com/thisiszhou/CTBZStock  
   收录：`strategy/backtrade/small_cap_demo.py`、`strategy/online/small_cap_demo.py`。  
   未收录：框架、数据库、在线交易其余部分。

5. **Daic115/alpha191**  
   https://github.com/Daic115/alpha191  
   收录：`alpha191.py`（约 93KB）。  
   未收录：`lib/`、`performace/`。

6. **hugo2046/QuantsPlaybook**（原误查 `charliedream1/QuantsPlaybook` 为 404）  
   https://github.com/hugo2046/QuantsPlaybook  
   全仓约 613MB，**禁止 clone**。  
   收录 SignalMaker 小文件：`README.md`、`qrs.py`、`vmacd_mtm.py`、`alligator_indicator_timing.py`、`utils.py`、`requirements.txt`。  
   未收录：全部 ipynb（含 ICU/RSRS/STR/球队硬币/筹码）、`hugos_toolkit`、研报 PDF。公式见 `playbook_notes.md`。  
   README 里的「平均年化 12.8%」等汇总表未核实，不要引用。

## 明确不拉

| 仓库 | 原因 |
|---|---|
| Harvey-Sun 相关大仓 | 凭据风险 + 体积约 187MB |
| CoCoMilkyWay/trade | 约 960MB |
| 任意 PDF | 任务禁止 |
| 带输出的 notebook | 任务禁止 |
| vnpy / qlib / rqalpha / backtrader 产品树 | 框架，不是策略 |

## 拉取失败

- `git clone https://github.com/WAYLON/ashare-quant-strategies.git`：代理 `Proxy CONNECT aborted`。zip 成功，文章已抽出。
- `https://api.github.com/repos/charliedream1/QuantsPlaybook`：404。正确仓库是 `hugo2046/QuantsPlaybook`。
- QuantsPlaybook 的 ICU/STR/球队硬币/筹码只有笔记本，未下载。
