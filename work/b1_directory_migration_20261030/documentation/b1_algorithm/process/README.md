# 正式B1过程组件

提供统一的回顾性过程识别入口。默认规则先通过独立开发集准入，再在新留出数据评价；调用时不要求使用者挑选候选方法。

```python
from b1_algorithm.process import identify_process
from b1_algorithm.process.batch import identify_process_batch

result = identify_process(starts_min, ends_min, power_kw, reference_kw,
                          task, noise_sigma_kw, config=runtime_config)
```

`task`需要非空字符串`task_id/user_id/meter_id`，以及`start_min=0`、`end_min=30`、`request_kw=1.5`、`notice_min=-15`。输入为完整规则计量格，覆盖−15至45分钟，支持10秒、1分钟、15分钟。参考预测应非负；有限带符号的计量值可以输入，会记录负读数个数并原样积分。缺测、缺噪声标准差、布尔或字符串混入数值数组及域外任务返回`unavailable`。

运行配置字段：`rscript_path`、`r_library`、`artifact_dir`、`timeout_seconds`。也可设置环境变量`B1_RSCRIPT/B1_R_LIBRARY/B1_RUNTIME_DIR`。组件通过CSV子进程调用原生CPOP，保留临时输入、原生结果及日志，不删除文件；批量入口共享一次R调用。R不可用或超时会返回`degraded/raw_F0`及原因，不会以模板静默替代原生方法。

内部规则：

- 只有4个计量格时保留原格值`raw_coarse`，不给格内物理时点。
- 信息量足够时以原生CPOP默认网格为保守起点。开发准入后的门控策略用5折交错1分钟块留出误差判断是否采用任务模板；至少降低10%验证MSE且块均值收益超过1个块标准误才采用。该规则是保守决策准则，不能解释为置信保证。
- 模板未通过、拟合失败或验证不可用时回到CPOP。默认策略及开发依据见`_policy.json`，不根据单次真实机制或仿真真值挑方法。

返回`status/method/reason/selection_evidence/features/eta_raw`。`features.selected_curve`是选定曲线上的原F0阈值/驻留特征；`features.raw_observed`保留原观测特征；二者均区分累计时长和最长连续时长。`features.accounting`及顶层`eta_raw`使用共同原始残差积分，包含请求电量、反弹和恢复/删失状态，不随拟合模型换算电量。

`physical_timing`始终为`None`，过程置信区间标为尚未验证。观测阈值结果、用户是否参与和真实物理动作不是同一量。参考预测误差与实际噪声条件需调用方另行提供证据。

来源见`SOURCE_ORIGIN.json`：原F0和RIDE积分模板保留原字节与SHA；任务模板拟合器为基于相同结构思想的新实现，增加成功状态与有限预算检查，不沿用作者自检成绩。正式Python源码不导入工作目录的临时代码。原生CPOP是明确的外部R依赖，已验证版本为1.0.10。
