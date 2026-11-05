# TF小型复现实现口径

`trend_filter.fit_curve(y, covariance, penalty)`复现标准凸目标

\[
P(x)=\tfrac12(x-y)'\Sigma^{-1}(x-y)+\lambda\|D_2x\|_1.
\]

本pilot直接以原生完整等宽计量格均值为x，H=I，不增加潜在格内节点或超分辨率。正式数据由调用方限制为60个1分钟格；函数容许n≥3以做小型独立数学控。covariance为完整SPD矩阵，或正标量方差（不是标准差）。不在事件内拟合自由参考偏移，不截幅，不读truth，不按强弱标签路由。

采用成熟凸对偶：\(x=y-\Sigma D_2'u\)，\(|u|\le\lambda\)。若\(\Sigma=LL'\)，以\(A=L'D_2'\)、\(b=L^{-1}y\)将对偶转为有界最小二乘，用SciPy `lsq_linear(method='bvls', tol=1e-12)`求解；独立计算primal、dual、间隙、可行性和KKT。primal-dual容差为\(10^{-8}+10^{-8}\max(1,|P|,|dual|)\)，还要求求解成功、有限和KKT通过，否则`unavailable/prediction=None`，无静默raw回退。λ=0返回精确未惩罚解并明确记录。

输出包含`status/prediction/primal/objective/dual/raw_gap/gap/gap_tolerance/gap_pass/success/optimality/kkt_residual/kkt_tolerance/kkt_pass/bound_violation/iterations/finite`及求解消息。微小负数间隙保留在raw_gap，gap展示截为0，但接受必须raw_gap位于正负容差内，不能掩盖大负间隙。

`control_trend_filter.py`只用构造小例：λ0、常数/直线、正负对称、物理单位缩放、固定Σ缩放、标量方差与σ²I、KKT/互补间隙、3例完整Σ与独立SLSQP primal epigraph求解对照、坏输入，以及故意虚报成功的solver结果必须被数学门拒绝。结果在`trend_filter_controls.json`。控数量不是性能样本；没有对研究数据做选择或评价。

运行环境固定已有`work/ride_b1_v02_reproduction_20261029/.venv/Scripts/python.exe -B`，数值线程1，无新依赖。数值控通过只确认复现计算，不证明未知参考下响应识别或性能优越。标准TF及GLS在本轮仅作内部复现/归因，特征提取正式对照按用户决定为原CP，不自动增加每模块baseline。

λ单位依赖y和Σ尺度：若功率整体放大c倍且Σ放大c²，保持同一物理解时λ应除以|c|。不得跨单位直接搬用λ网格。完整非事件预测残差已包含计量噪声时，调用方不得重复加入同一噪声方差；Σ如何估计与选择由独立协议决定。
