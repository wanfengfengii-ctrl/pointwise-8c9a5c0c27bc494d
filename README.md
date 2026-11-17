# CRisk 离线竞争风险分析

Python 3.11 标准库项目，无安装步骤。登记随访观察段、原子接纳更正、冻结分析队列，计算精确加权 Aalen–Johansen 累计发生概率及按受试者聚类的完整联合协方差，再将结果归档至 SQLite。单工作者离线使用；一个 App 拥有一个连接。

## 运行

在项目根目录执行：

```sh
python3.11 -B -m unittest discover -s tests -v
python3.11 -B -m crisk demo
```

demo 在自己的临时目录中创建真实数据库，登记 samples/joint.json，生成报告，更正观察段，生成新报告，关闭重开后读取并重算旧队列。输出三行 JSON。也可使用新的项目内路径运行 `python3.11 -B -m crisk demo --db demo.sqlite`；重复使用已有 demo ID 且内容不同时会拒绝。

CLI 每次调用都会关闭连接，因此下列调用也是重开读取流程：

```sh
python3.11 -B -m crisk apply --db analysis.sqlite samples/joint.json
python3.11 -B -m crisk freeze --db analysis.sqlite c1 4 1 5 --causes 2 1
python3.11 -B -m crisk analyze --db analysis.sqlite c1 r1
python3.11 -B -m crisk read --db analysis.sqlite r1
```

每条业务命令输出一条 JSON。业务校验、未知 ID、文件和数据库错误输出含 error 的 JSON，退出码 2。argparse 参数错误也退出 2。回调异常由 Python API 原样传播。所有路径均由调用者指定；程序只读取指定输入及自己的样例、数据库或测试临时目录。

## 数据与修订

观察段 JSON 严格包含 subject、segment、revision、weight、enter、exit、event 七字段。ID 是非空字符串，按原值区分，不做大小写或空格归一化。revision 是正整数。event 是整数 0（删失）、1 或 2（互斥终末事件）。布尔值不当作整数。

有理数接受 JSON 整数或字符串，例如 "3/2"、"-1"；分母须为正整数。Python API 还接受 Fraction。拒绝浮点数、布尔值、非有限值及零分母。权重严格为正，进入时刻严格早于退出时刻；时间允许负值。

同一 segment 每批最多一次。已接受的同版同内容幂等，已接受的同版不同内容冲突，低于当前最高版本的未知旧版忽略，不登记为新历史；更高版本替换当前值。完整最终有效历史须满足同一受试者权重一致、观察段不重叠、终末事件后无后续观察段。删失后可以重入；前段退出等于后段进入合法。批次按最终历史一起校验，允许同时修正相关段。任一错误整批回滚，当前账、历史、epoch 和已有报告均不变。非空有效修改批次使 epoch 加一；Receipt 返回 epoch 和排序后的 changed 段 ID。

crisk/ledger.py 负责修订接纳及历史合法性；crisk/storage.py 保存已接受的修订历史和当前最高版。没有撤回或删除接口。

## 冻结与 Python API

```python
from crisk import App, Observation

with App("analysis.sqlite") as app:
    receipt = app.apply([
        Observation("A", "a", 1, 1, 0, 2, 1),
        Observation("B", "b", 1, 1, 0, 2, 2),
    ])
    cohort = app.freeze("two", [2, 0, 2], causes=(2, 1))
    report = app.analyze("two", "joint")
    assert str(report.probabilities[0]) == "1/2"
    assert str(report.covariance[0][1]) == "-1/8"
    assert app.read("joint") == report
```

App() 默认使用内存数据库；App(path) 在不存在时创建数据库。apply 接收 Observation 或严格字段字典的可迭代批次。freeze(cohort_id, times, causes=(1,2)) 将当前有效观察段的完整副本、source_epoch、请求时刻及原因顺序原子保存。times 是非空有理数序列，可无序、可重复；causes 必须是 (1,2) 的排列。空观察账可冻结。输入在调用后修改不会改变队列。cohort(id) 返回冻结内容；未知 ID 抛 KeyError。

队列 ID 不可重新绑定：同内容且同 source_epoch 可重放，否则 ValueError。后续更正不修改旧队列；旧队列可重新分析。crisk/cohort.py 拥有冻结状态。

analyze(cohort_id, report_id, before_commit=None) 从该冻结队列计算并发布；read(report_id) 读取报告。报告 ID 同内容重放，不同内容冲突。返回的 Observation、Cohort、Report、Receipt 都是冻结 dataclass，内部序列为 tuple；Report.record() 生成可修改的独立 JSON 字典，有理数编码为字符串。app.ledger.current() 返回有效观察段，app.ledger.epoch 返回当前 epoch，app.archive.ids() 返回排序的报告 ID。

## 统计语义

对时刻 t，风险集由 enter < t 且 exit >= t 的观察段组成。同刻事件共同使用一个事件前风险集；同刻删失仍在分母中，同刻新进入者不在其中。crisk/risk.py 将各事件时刻的风险和事件贡献按 subject 保留。合法历史保证同一受试者在同一事件时刻最多贡献一个有效观察段。

记事件前生存为 S，风险总权重为 Y，两原因事件权重为 d1、d2。使用原 S 同时更新 F1 += S*d1/Y、F2 += S*d2/Y，然后更新 S *= 1-(d1+d2)/Y。初值 S=1、F1=F2=0。查询取不晚于请求时刻的全部事件；事件前查询为零发生概率。风险耗尽后 S 为零，即使以后其他受试者进入，已定义的累计概率仍依递推保持不变。零事件报告 S=1、F1=F2=0。

crisk/report.py 对每名受试者引入共享倍率 z，其所有观察段在所有时刻的风险贡献和事件贡献一起乘 z。在全部倍率为 1 处精确求导。每个请求时刻依 causes 顺序形成坐标；请求顺序和重复均保留。covariance[i][j] 是各受试者第 i、j 坐标梯度乘积之和，不作有限样本修正。全部结果均为 Fraction。survival 与请求时刻一一对应；probabilities 与 coordinates 一一对应；covariance 是这些概率坐标的完整方阵。生存值的协方差不属于当前输出。

两人同刻分别发生两种事件，权重均为 1 时，概率为 (1/2,1/2)，协方差为 ((1/8,-1/8),(-1/8,1/8))。samples/joint.json 同时包含同刻事件、删失、严格延迟进入和跨段共享受试者；时刻 4 的 (F1,F2)=(3/8,7/16)，时刻 5 为 (9/16,7/16)。当前计算采用完整事件扫描及逐受试者方向重算，适合有限离线队列，不宣称大规模处理性能。

## 归档与失败边界

crisk/archive.py 在一个 SQLite 事务中保存报告 ID、队列绑定和精确结果；有理数不经过浮点。before_commit 是无参数可调用对象，仅在新报告插入后、提交前调用，用于接入本地提交前检查；异常使整次发布回滚。重试可使用相同报告 ID，已有报告不变。该回调不应开启另一个写事务。未知队列、非法请求或计算失败不产生报告。读取从存储重新解码，不共享可变容器。App 必须显式 close 或作为上下文管理器使用。

数据库格式为 user_version=1：metadata 保存 epoch；history 保存已接受的观察段修订 JSON；current 保存最高版；cohorts 保存完整冻结副本；reports 保存绑定及完整结果 JSON。报告外键指向队列。SQLite 自身事务承担提交和回滚；不支持多个工作者共享 App、在线服务或其他格式数据库。

## 回归

tests/test_analysis.py 检查手算两原因、延迟进入与同刻退出的 24 种排列、重入身份、全部请求坐标、合法拆段、共同权重缩放、零事件、风险耗尽及 27 个小队列。tests/oracle.py 直接从原始观察段展开多项式乘积和商，以独立商法则核对全部概率及协方差，不调用生产风险加工或传播代码。

tests/test_ledger.py 检查字段、同版冲突、旧版忽略和非法历史整批拒绝。tests/test_history.py 检查输入/输出隔离、更正前后报告和关闭重开。tests/test_archive.py 在真实临时数据库检查未知队列、提交前故障、跨连接不可见性和重开重试。tests/test_cli.py 实际启动 CLI，核对公开样例、退出码及 demo。完整 discover 为正式验证入口。

本项目不提供回归模型、置信区间、第三种原因、多状态转移、增量分析或可视化服务。
