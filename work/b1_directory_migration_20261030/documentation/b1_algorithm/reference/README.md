# B1参考功率正式模块 v1

默认方法为固定SafeGBDT，辅助方法为已有非事件历史均值`prev10`。模型参数和九项特征保持已比较版本，不默认启用没有额外收益的自动选择器。

公开接口在`__init__.py`导出：`ReferenceWindow`、`ReferenceTrainingRecord`、`WindowCalibrationRecord`、`fit_reference`、`predict_reference`、`calibrate_window_reference`、`save_reference_model`和`load_reference_model`。

所有时刻使用同一绝对分钟原点。当前域为EV/AC、完整1分钟计量、任务30/60分钟、通知提前15/30/60分钟、任务相对[-120,90]分钟内的参考网格。预测输入包括完整通知前60分钟功率前缀、此前可用的日历和温度条件、至少两条已有非事件历史曲线的均值及来源ID/可用时刻。缺字段、通知后数据、未来可用时刻、非有限数、布尔/字符串数值、任务或网格越界时返回`unavailable`，不会以实际离站、未来会话或事后电量补齐。

历史训练记录提供各自通知前特征和已完成的非事件标签。训练标签必须在模型拟合截止前可用；预测时模型必须在事件通知前已拟合。模型默认拒绝训练用户或校准用户混入留出预测；只有显式`allow_seen_user=True`才允许用合法历史作运营预测，并返回seen-user标记，不能把它计为独立用户评价。

输出`ReferencePrediction`绑定task/user/meter三个ID、计量网格以及任务起止、请求功率和通知时刻，给出状态、方法、模型ID及可用时刻。统一入口应同时检查这些任务定义，避免同ID下误改请求或通知后继续复用参考及按q归一的窗口带。它是功率预测，`counterfactual_identified=False`。可选校准半宽仅适用于整任务窗归一残差的用户块统计量，不能作为逐点噪声σ或细时点置信带；伪事件到实际事件的分布迁移不由接口保证。校准样本不足时半宽为`None`。

模型存为LightGBM原生`model.txt`和JSON元数据，不加载pickle。载入检查schema、字段、九项特征、固定参数、LightGBM版本、模型SHA、模型ID、用户角色和校准字段。SHA用于一致性校验，不证明文件来源可信；只加载调用方明确选择的本地模型目录。现有artifact不覆盖，保存时须选择新目录。

`model_id`仅标识原生booster数值模型；重新校准不会改变这一数值模型身份。校准状态保存在独立JSON元数据中，整体元数据SHA另由来源/交付清单记录，因此不能只凭`model_id`判定两份校准状态相同。

本模块独立于RIDE的ObsData、生成器和任何work路径。时间戳与历史来源需要调用方提供真实证据，程序只能检查声明之间的时序一致性，不能验证一项外部事实是否被如实申报。
