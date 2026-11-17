# analyze 联合优化交接说明

## 改动范围与保留接口

只改 `crisk/risk.py` 与 `crisk/report.py`，其余业务（登记、更正、冻结、归档、CLI、演示）未动。

- `crisk/risk.py`：`RiskFrame` 与 `build_risk` 逐字保留（tests 直接使用的兼容入口，仍产生密集成员快照）。新增 `sweep(observations)`：一次排序加权重前缀和扫出每个事件时刻的风险总权重、两原因事件权重，并按受试者归组每行的权重、风险窗口 `(lo, hi]`（事件时刻下标）与终末事件原因。
- `crisk/report.py`：`calculate(cohort, report_id)` 签名不变，不再逐受试者重算 `Direction` 前向链。正向递推只求点值（S、F1、F2）；每个请求概率坐标做一次反向伴随递推，得到每个事件时刻的系数（风险窗口 A、事件 B1/B2），受试者梯度 = Σ_k A_k·y_k^s + Σ B_c,k·δ_c,k^s，按受试者合并全部观察段后再做外积累加协方差。`invalid risk contributions` 校验与报错语义保留。

接口、旧库读取、冻结队列、报告重放/冲突、before_commit 回滚、关闭重开语义均不变；未新增分析能力。

## 贡献归属与传播不变量

- **重入共享身份**：同一受试者的全部观察段共享一个倍率 z。`sweep` 按 subject 精确归组，梯度先在受试者内合并（各段窗口系数和 × 段权重 + 事件系数），再对坐标求外积；把后段改成另一受试者会得到相同概率、不同协方差（差分脚本与 optimization_checks 均核验）。
- **同刻边界**：风险集保持 enter < t ≤ exit。同刻事件共用事件前分母（Y 在事件时刻一次性取 aggregates）；同刻删失仍在分母（exit = t 计入窗口右端）；同刻新进入者不参与（enter = t 被 `bisect_right` 排除）；删失后退出、进入前不参与由窗口 `(lo, hi]` 天然表达。
- **零生存因子**：某事件时刻 D = Y 后 S = 0。正向递推继续走完全部事件时刻（已定义累计概率不再变化）；伴随系数中 S=0 之后的 A、B 均为 0，与参照的 Direction 传播一致。空队列、事件前请求、风险耗尽后再有进入者均按原递推处理。
- **精确性**：伴随系数是同一全导数的线性重组，所有运算为 Fraction 精确算术，加法可交换结合，故与冻结参照逐位相等（基准中 digest 一致）。

## 实测（本机，三轮中位数）

| 负载 | 参照 | 目标 | 比值(≤1/8) | 增长(≤6) | 峰值(≤32MiB) |
|---|---|---|---|---|---|
| long 64 | 0.267s | 0.0126s | 0.047 | 3.19 | 102,896 B |
| long 256 | 13.38s | 0.0401s | 0.003 | | 362,488 B |
| reentry 64 | 0.235s | 0.0128s | 0.055 | 3.56 | 125,168 B |
| reentry 256 | 11.41s | 0.0458s | 0.004 | | 446,808 B |

## 复跑方式

```sh
python3.11 -B -m unittest discover -s tests -v   # 原回归（14 项，逐字保留）
python3.11 -B optimization_checks.py baseline   # 业务基线核验
python3.11 -B optimization_checks.py target    # 联合核验（verify 入口）
python3.11 -B bench_analysis.py target --kind long --subjects 64   # 单案例
python3.11 -B differential_checks.py           # 独立差分与边界核验
python3.11 -B -m crisk demo                    # 真实登记/更正/冻结/分析/重开演示
```
