# Frozen continuous独立交叉审查

2026-10-30。审查对象为根 `B1算法/b1_algorithm/effects/frozen.py`，本轮源码SHA256：`09c7fb84bbaa7e140cd985a034456b2db477df6f00427665bb0a0c9fbaa5c03c`。本审查未改源码、旧数据或主分数，未运行新主研究。`audit.py`是独立编写的小型数学/合同反例，不复述原33项检查。

**未发现数学P1。发现两类P2输入合同缺口，已即时交给root修复；当前合法fit生成的模型不受这两个反例影响。** 截至本意见冻结，39个断言35通过、4个失败；4个失败对应下列真实合同缺口，并非研究性能失败。

## 1. 数学和行为核验

独立生成960行/240用户、每人4行的非单调、异方差并含用户效应的数学cohort，使用整数用户ID。拟合并查询后，与原 `continuous.py` 在相同X、D、结果、用户、任务、随机种子和查询grid上核对：三个不同grid（含单独reference）均值、contrast和条件带标准误/上下界一致，容差1e-10。另以估计GPS的观察路径复核，均值与条件带上界同样一致；未用新候选之间相互印证替代原内核比较。

将完整冻结非线性均值曲线在六个不等间距点、含域两端作中心差分，灵敏度公式与数值导数最大差约4.02e-9。另核导数不等于随手取局部直线斜率；金额乘37后导数按1/37缩放。由公式看，权重关于查询点变化的分子和分母导数均纳入，符合所声称的“冻结平滑均值的导数”。

同时阻断公开拟合函数和底层crossfit后，query、灵敏度、阈值及根细化仍可运行，模型payload不变，没有查询时重训。

阈值反例覆盖：两个分离的非单调上穿、每个根代回同一冻结曲线、已到达搜索左端的明确左截断、平坦零结果未达、显式支持失败、association不输出因果候选带。实际mesh最大间隔不超过用户设定。输出保留`continuous_threshold_coverage_validated=False`和`optimal_price=False`，不能把这些条件有限网格候选解释为连续因果阈值置信集。

## 2. 两类P2合同问题

### A. known_density_used没有严格布尔校验

位置：`_payload`中将JSON字段直接传给`validate_assumptions(...,has_known_pi)`。构造checksum一致的合法结构模型，声明`randomized_assignment=True`、`conditional_exchangeability=None`，仅将`known_density_used`分别改为整数1、字符串`"false"`，二者均被接受并返回`causal`。空list/dict则因假值而拒绝。

这说明字段按Python真值而非JSON布尔合同判断。建议模型加载层显式要求原生布尔，不能依靠调用方已正规生成。该反例需要自行修改payload并重算checksum；它说明合同薄弱，不说明checksum能证明来源，也不推翻正常fit生成的合法bool模型成绩。root已确认将补严格校验。

### B. 非字符串payload导致内部AttributeError

直接构造`FrozenContinuousModel(payload_json=None, sha256='x')`，query抛`AttributeError: NoneType has no attribute encode`；JSON envelope将`payload_json`设数值123，load同样抛`AttributeError`。建议在编码和解析前核outer envelope、payload_json与sha256类型，并统一为明确ValueError；同时严格拒非有限JSON与错误嵌套结构。

上述两个反例均被拒绝继续计算，但异常属于实现细节而非可操作合同错误，会使只捕获ValueError的上层处理失效。当前合法模型往返和查询不受影响。

## 3. 审查脚本纠错和留痕

首次 `audit_initial.py`/`receipt.json` 有31通过、6失败。两项为审查脚本假设错误：

1. 左端已达到目标时，最早可报告位置是左截断搜索起点，可以早于`point_crossings`里的后续上穿，不能要求两者相等。
2. 全域边界不必然支持不足；本cohort在0和2.4附近仍有足够局部信息，不能仅因查询到端点就预期unsupported。

已纠正为“最早位置不晚于后续根”，并通过提高局部事件下限构造明确支持失败，再另加观察GPS路径核验。二次结果在 `round2/receipt.json`：35通过、4合同失败。初次脚本和失败收据完整保留，不将审查脚本错误记为算法bug。

## 4. 结论和复核要求

冻结的科学机制、导数和有限mesh阈值语义通过本轮独立核验；源码当前两类P2合同缺口待root修复。修复应保留本SHA对应的研究源码与原结果，先在合法既有模型上逐项查询等价复放，再补上述坏类型反例，不为此重新选模型、重跑科学研究或改动成绩。

本意见只评价现有冻结内核，不验证不可观察混杂、完整误差覆盖、真实EV效用、最优价格或研究点一全部完成。
