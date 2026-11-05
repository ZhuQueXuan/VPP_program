# 固定 EV 参考误差候选

正式源码为 `B1算法/b1_algorithm/reference/reliable.py`，不修改旧参考模型、历史选择或默认调用。

```python
from b1_algorithm.reference.reliable import (
    fit_ev_reference_error_model, predict_ev_reliable_reference,
    save_ev_reliable_reference_model, load_ev_reliable_reference_model,
)

model = fit_ev_reference_error_model(non_event_records, fit_cutoff_min, seed=0)
save_ev_reliable_reference_model(model, "new_model.json")  # 必须是尚不存在的文件
model = load_ev_reliable_reference_model("new_model.json")
prediction = predict_ev_reliable_reference(model, reference_window)
```

`non_event_records` 为已有 `WindowCalibrationRecord` 的非空列表/元组。必须显式声明 `non_event=True`，全体标签端点完成且可得不晚于拟合截止；重复任务 ID、错身份、布尔/字符串数值和非有限数值均拒绝。所有记录和查询限 EV、W=30min、q=1.5kW、提前15min通知、任务相对 `[-15,45]` 的完整60个一分钟格。每条窗口已有的参考接口验证照常执行，包括历史非事件来源声明、数量和来源 ID、完整通知前历史和可用时间；来源事实性仍由调用者保存的原始记录保证。

每条记录以当前通知前完整60分钟（任务相对 `[-75,-15]`）均值为锚。四个15分钟块均值减锚；历史参考曲线减自身均值构成 shape。固定5结点三次样条共6个非冗余基函数，加四块与六基函数的24个交互，再加 shape，共31个特征。回归目标是非事件实测未来功率减锚；完整60格均进入训练。StandardScaler 后固定 Ridge alpha=10；无模型搜索，无已知模拟周期特征。原生 B-spline 的结点和结果与本机 sklearn 的 `SplineTransformer(n_knots=5, degree=3, knots='uniform', include_bias=False)` 精确一致。

模型采用不可变字符串保存原生 JSON 数值及 SHA256，无 pickle 或 Python 拟合对象。加载重核结构、固定域、系数维度、有限数、正缩放及 checksum；保存拒绝覆盖。checksum 只能检查完整性，不认证来源。查询不重训，模型截止及所有输入必须早于或等于本次通知；合法训练用户后续可查询，role 标作 `seen_training_user`，研究流程另外强制人群隔离。负预测整条返回 `unavailable`，不截顶。输出保留任务、用户、表计、格和任务定义绑定，可得时点取模型截止与输入可得时间之最大值；不编造点噪声、经验带或实际反事实识别结论。

`check_reference.py` 的 60 项小控已通过，证据在 `control_initial.log` 与 `control_receipt.json`。包括常数精确、查询和训练整体平移、与独立完整格 Ridge 数值对照、时间和身份错误、有限数类型、负预测、不可变和 JSON 校验。构造用负目标只用于检验负预测拒答，不是训练研究数据。`control_*model.json` 和畸形 JSON 是明确的小控工件。

截至本记录，仅完成实现与构造小控；未运行主研究、未证明真实反事实可识别、未宣称预测改善或现场可靠性。
