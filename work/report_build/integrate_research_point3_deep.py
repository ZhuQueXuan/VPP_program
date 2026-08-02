from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.text.paragraph import Paragraph


REPORTS_DIR = Path("outputs/reports")
SOURCE_NAME = "技术报告-课题一-虚拟电厂多元异质资源调节行为分析与智能分类方法-第三版-研究点一二深度扩写版.docx"
OUTPUT_NAME = "技术报告-课题一-虚拟电厂多元异质资源调节行为分析与智能分类方法-第三版-研究点一二三深度扩写版.docx"


SECTION_4_CONTENT = [
    ("h2", "4.1 研究定位与建模对象"),
    (
        "p",
        "虚拟电厂资源可调容量与响应能力特征建模，是把前两章的影响因素分析和机理模型转化为可计算模型输出的核心环节。"
        "第二章回答“哪些因素影响资源行为”，第三章回答“意愿与能力如何共同形成可信可调用能力”，本章进一步回答“如何把这些因素转化为模型输入、"
        "如何计算资源在某一时刻和某一市场场景下可调多少、能响应多快、能持续多久、可信度有多高”。因此，本章不是重复讨论调节意愿和动态能力的机理，"
        "而是围绕特征工程、容量边界、响应能力向量、资源专属模型、聚合修正和精度验证建立工程化建模方法。"
    ),
    (
        "p",
        "本研究建议将虚拟电厂资源能力分为五个层级：额定容量、理论可调容量、状态可用容量、可信可调用容量和市场有效容量。额定容量来自设备台账，只能反映设备名义上限；"
        "理论可调容量由设备物理约束和业务安全约束决定；状态可用容量进一步考虑SOC、在线车辆、生产状态、室内温度、光伏出力等实时状态；可信可调用容量在状态可用容量基础上"
        "叠加调节意愿、历史可靠度、通信控制可达性和不确定性折减；市场有效容量则根据具体市场对响应速度、持续时间、调节精度、最小申报容量和考核规则进行筛选。"
        "这样的分层有助于避免将装机容量直接等同于可交易能力，也便于解释模型结果。"
    ),
    (
        "p",
        "本章建模对象包括两类输出。第一类是可调容量特征，主要描述资源在给定时间窗口内的向上/向下调节功率边界和可调电量边界；第二类是响应能力特征，"
        "主要描述资源从接收指令到形成有效响应的时延、爬坡速率、持续时间、跟踪精度、恢复时间、反弹风险和可用概率。二者共同构成后续智能分级分类的基础特征，"
        "也是项目提出“模型精度不低于90%”要求的主要评价对象。"
    ),
    ("h2", "4.2 基线、可调容量与响应能力定义"),
    (
        "p",
        "可调容量建模首先必须明确基线。对于负荷型资源，基线P_base(t)表示未参与调节时的预计用电功率；实际响应量通常由基线功率与实际功率之差得到。"
        "对于发电型或储能型资源，基线既可能表示计划出力，也可能表示市场申报曲线或调度前预测曲线。若基线不准确，可调容量和响应效果都会被系统性高估或低估。"
        "需求响应文献中也指出，基线方法既关系到补偿结算，也关系到响应效果评价，甚至可能引发基线操纵问题[14]。因此，本课题应把基线预测作为可调容量建模的前置环节。"
    ),
    (
        "p",
        "在统一符号上，可将资源i在时刻t、预测窗口H内的向上可调功率记为P_up,i(t,H)，向下可调功率记为P_down,i(t,H)，可调电量记为E_i(t,H)。"
        "其中，“向上”和“向下”应在项目中统一正负方向：可以按虚拟电厂对外等效出力增加/减少定义，也可以按用户侧负荷增加/减少定义，但正式建模前必须固化口径。"
        "响应能力可表示为R_i(t,H)=[tau_i, ramp_i, dur_i, acc_i, rec_i, prob_i]，分别对应响应时延、爬坡速率、可持续时长、跟踪精度、恢复时间和可用概率。"
    ),
    (
        "p",
        "与单一容量指标相比，上述定义更适合多元市场应用。现货移峰场景关注可调电量、持续时间和成本，备用场景关注可用概率、通知提前量和保持时间，"
        "调频或快速响应场景关注响应时延、爬坡速率和跟踪精度，需求响应场景关注基线可核验性、完成比例和反弹风险。"
        "因此，可调容量与响应能力特征模型应输出能力向量，而不是只输出一个“可调容量”数值。"
    ),
    ("h2", "4.3 数据基础与特征工程框架"),
    (
        "p",
        "本项目已经在多维行为特征库数据字典中设计了资源主数据、资源运行状态时序、外部环境时序、市场信号、用户行为、调节事件、调节结果和行为特征等主题表。"
        "第四章的建模方法应明确这些主题表如何进入模型。资源主数据提供额定功率、资源类型、聚合单元、地理位置和设备属性；资源运行状态时序提供实时功率、可用状态、SOC、"
        "设备告警和业务状态；外部环境表提供温度、湿度、辐照度、节假日和区域负荷；市场信号表提供价格、补偿、考核和市场类型；用户行为表提供授权、接受、拒绝和退出信息；"
        "调节事件与调节结果表则提供模型训练和验证所需的标签。"
    ),
    (
        "p",
        "特征工程可分为基础特征、状态特征、窗口特征、交互特征和结果反馈特征。基础特征描述资源固有属性，例如资源类型、额定功率、容量、接入电压等级和所属聚合单元；"
        "状态特征描述当前可用性，例如SOC、在线车辆数、当前负荷、室内温度、生产状态和通信状态；窗口特征描述过去一段时间的行为，例如近7日负荷均值、近30日响应成功率、"
        "相似天气下负荷分位数和最近一次调用后的恢复时间；交互特征描述市场、天气和状态的耦合，例如高价差*SOC、高温*空调负荷、通知提前量*用户授权等级；"
        "结果反馈特征则将历史响应偏差、收益、考核和反弹情况反馈到下一周期建模。"
    ),
    (
        "p",
        "时间对齐是特征建模的关键质量控制点。市场价格可能是15分钟或小时级，气象数据可能是分钟级或小时级，设备监测可能是秒级或分钟级，调节结果则按事件窗口统计。"
        "如果直接拼接不同粒度数据，容易出现特征错位和标签泄漏。因此，建议以调节事件或市场申报窗口为主索引，将调节前状态、调节中响应、调节后恢复分为不同特征窗口，"
        "并明确哪些特征在决策时刻可获得，哪些只能用于事后评价。"
    ),
    ("h2", "4.4 分资源可调容量建模方法"),
    (
        "p",
        "分布式光伏的可调容量建模应以预测出力、当前出力、可控限发空间和配储状态为核心。光伏向下调节容量可以由当前出力、逆变器控制能力和并网约束确定；"
        "向上调节容量通常取决于前期是否存在限发基线或是否配置储能。对无配储光伏而言，向上能力不宜简单按装机容量与当前出力差额计算，因为辐照变化和预测误差可能导致该空间不可控；"
        "对光伏加储能资源，应将光伏预测曲线与储能SOC、充放电功率和容量约束联合建模。"
    ),
    (
        "p",
        "储能可调容量建模应同时考虑功率边界和能量边界。其向上或向下能力受额定功率、SOC上下限、可用容量、充放电效率、温度、SOH和后续运行计划约束。"
        "若只使用额定功率计算响应能力，容易忽略持续时间和容量饱和风险。相关灵活性建模研究也强调，储能和柔性负荷需要同时考虑功率、能量、爬坡和截止时间等约束，"
        "否则会高估或低估实际可用能力[12]。因此，储能模型应输出不同持续时间下的可调功率曲线，而不是单点容量。"
    ),
    (
        "p",
        "充电桩和充电站的可调容量来自在线车辆集合，核心约束包括站内容量、正在充电车辆数、当前SOC、目标SOC、剩余停车时间、最小保障电量和用户授权。"
        "向下调节可以通过降低充电功率或延迟充电实现，向上调节可以通过提前充电或在V2G条件下放电实现。其模型应采用车辆级能力聚合到站级，再由站级聚合到区域级，"
        "并在每一层考虑离站不确定性和用户授权折减。"
    ),
    (
        "p",
        "工业可调负荷的容量模型应从工艺和生产组织出发，而不是只根据历史负荷波动推断。可中断负荷、可转移负荷、可削减辅助系统和可调储能/自备电源应分别建模。"
        "对连续型生产负荷，应重点识别安全边界、最短停机时间、恢复时间和产品质量风险；对批处理或可排程负荷，应重点识别可移峰窗口、库存缓冲和订单交付约束。"
        "工业负荷模型输出应包含可削减功率、可持续时间、可恢复时间和不可调用原因。"
    ),
    (
        "p",
        "商业楼宇和空调负荷的可调容量建模应结合热惯性模型与数据驱动修正。短时能力来自设定温度调整、预冷预热和群控策略，持续时间受室内外温差、人员密度、舒适边界和投诉风险约束。"
        "响应结束后，空调负荷可能出现反弹，因此模型不仅要估计调节期间的削减容量，还要估计恢复阶段的补偿负荷。大规模热泵需求响应实证研究表明，建筑热负荷的响应潜力可以通过"
        "计量数据和室外温度识别，但反弹抑制同样是评价效果的重要组成部分[15]。"
    ),
    ("h2", "4.5 响应能力特征建模方法"),
    (
        "p",
        "响应能力特征建模关注资源能否按市场任务要求完成动作，而不仅是能调多少。响应时延可定义为指令下发到实际功率达到阈值的时间差；爬坡速率可定义为单位时间内功率变化量；"
        "持续时间可定义为资源在不突破安全、舒适和业务边界条件下维持响应的最长时间；调节精度可定义为实际响应曲线与目标曲线在考核窗口内的偏差；"
        "恢复时间可定义为响应结束后资源回到正常运行区间所需时间；可用概率则反映在当前状态和不确定性条件下完成任务的置信程度。"
    ),
    (
        "p",
        "这些响应能力特征应结合市场场景分别计算。对调频类场景，应重点计算秒级或分钟级时延、跟踪误差和高频动作限制；对削峰填谷或现货移峰场景，应重点计算可持续时长、"
        "可调电量和恢复反弹；对备用场景，应重点计算通知提前量、保持时间、可用概率和失败概率；对需求响应场景，应重点计算基线误差、完成比例和事后核验一致性。"
        "换言之，同一资源在不同市场中的响应能力标签可以不同，不能用单一综合分数替代场景化能力。"
    ),
    (
        "p",
        "响应能力模型应采用“事前预测、事中跟踪、事后校准”的闭环。事前预测阶段根据资源状态、市场任务和历史表现估计能力；事中跟踪阶段根据实际功率曲线修正剩余可调容量和持续时间；"
        "事后校准阶段根据响应偏差、失败原因和恢复反弹更新模型参数。这样可以支撑虚拟电厂在调节任务执行过程中动态调整资源组合，避免一次申报后长期不修正带来的履约风险。"
    ),
    ("h2", "4.6 主观意愿与客观能力一体化特征"),
    (
        "p",
        "可调容量和响应能力最终需要从“理论可用”转化为“可信可调用”。因此，本章在特征建模中引入主观意愿修正、历史可靠度修正、通信控制可达性修正和安全校核修正。"
        "主观意愿修正来自第三章的W_open，用于表示用户愿意开放的能力比例；历史可靠度修正来自过去调节事件的完成率、响应偏差、退出频次和考核结果；"
        "通信控制可达性修正用于处理设备离线、数据延迟、控制失败等问题；安全校核修正用于剔除可能突破设备、电网、生产或舒适边界的能力。"
    ),
    (
        "p",
        "综合特征可表示为A_i(t,m,H)=Phi(C_i(t,H), W_i(t,m), Q_i(t,m), R_i(t), S_i(t))。其中C表示客观能力向量，W表示意愿开放程度，"
        "Q表示市场场景匹配程度，R表示历史可靠度，S表示安全校核结果，Phi表示融合函数。第一阶段可采用规则加权和分段折减的可解释方法，便于向评审说明模型逻辑；"
        "数据积累后，可引入广义加性模型、梯度提升树、随机森林、图模型或时序深度学习模型进行非线性修正，但仍应保留物理约束和安全边界作为硬约束。"
    ),
    (
        "p",
        "这种一体化建模方法的优点是可解释性较强。模型不仅输出“该资源当前可调容量为多少”，还可以输出限制因素，例如SOC不足、剩余停车时间不足、舒适度边界不足、"
        "用户授权不足、历史可靠度偏低或市场任务不匹配。限制因素解释对于虚拟电厂运营尤其重要，因为它能够把模型结果转化为资源邀约、补偿设计、状态预充、组合调度和用户沟通策略。"
    ),
    ("h2", "4.7 聚合层能力建模与网络约束"),
    (
        "p",
        "虚拟电厂对外参与市场时，申报和履约通常以聚合单元为对象，因此需要将单资源能力进一步聚合。聚合容量不能简单等于单体容量之和，原因包括资源可用性相关、响应时间不同、"
        "控制链路不同、地理位置不同、配电网约束不同以及市场规则对最小容量和组合曲线的要求不同。已有虚拟电厂灵活性研究区分了可行运行域和灵活性运行域，指出网络拓扑、"
        "快慢资源组合和服务类型会影响虚拟电厂可对外提供的能力范围[11]。"
    ),
    (
        "p",
        "聚合层建模应至少考虑三类修正。第一是同时可用性修正，即不同资源在同一时间窗口内同时满足意愿、状态和控制条件的概率；第二是曲线形状修正，即聚合后响应曲线是否满足"
        "市场目标曲线的速度、持续和精度要求；第三是网络安全修正，即资源响应是否会引起局部线路、变压器、电压或功率因数约束问题。对于具备配电网模型的区域，"
        "可进一步构建可行功率转移区域，保证虚拟电厂对外申报的聚合能力在网络层面可实现[13]。"
    ),
    (
        "p",
        "在项目当前阶段，如果配电网详细模型和实时潮流数据暂不可得，可先采用分层聚合和保守折减方法：先在资源级计算能力，再在站点级或用户级汇总，随后在聚合单元级按照历史同时响应率、"
        "通信可用率和安全冗余进行折减，最终形成市场申报能力。待后续具备更完整网络数据后，再将配电网约束、节点位置和潮流校核纳入模型。"
    ),
    ("h2", "4.8 模型训练、校准与不确定性估计"),
    (
        "p",
        "可调容量与响应能力特征模型的训练标签来自调节事件和调节结果。容量类标签可由基线功率、目标功率、实际功率和完成比例构造；响应类标签可由响应时延、爬坡速率、跟踪误差、"
        "持续时间、退出事件和恢复反弹构造；可靠度标签可由是否完成、偏差是否超限、是否被考核、是否出现通信或控制失败构造。训练样本应按时间、资源类型和市场场景划分，"
        "避免同一资源相邻事件同时出现在训练集和测试集导致过高估计模型精度。"
    ),
    (
        "p",
        "模型校准应遵循“物理先验+数据修正”的路线。对光伏、储能、充电站、工业负荷和楼宇空调，先用物理和业务规则确定能力边界，再用历史事件数据校准边界折减系数、可靠度参数和不确定性范围。"
        "对于样本较少的资源，可采用同类资源迁移、专家参数初值和贝叶斯更新；对于样本较多的资源，可采用监督学习、分位数回归或概率预测方法输出置信区间。"
        "概率化输出比单点预测更适合市场申报，因为虚拟电厂需要在收益和履约风险之间权衡。"
    ),
    (
        "p",
        "不确定性估计应覆盖输入不确定性、模型不确定性和执行不确定性。输入不确定性来自天气、价格、车辆到离站、生产计划和用户授权变化；模型不确定性来自样本不足、特征缺失和模型结构假设；"
        "执行不确定性来自通信延迟、设备故障、控制失败和人为干预。模型输出可采用P50/P90能力、保守能力和激进能力三类口径，分别服务于计划评估、稳健申报和潜力挖掘。"
    ),
    ("h2", "4.9 精度评价与90%指标落地"),
    (
        "p",
        "项目要求构建虚拟电厂多资源可调容量与响应能力特征模型，模型精度不低于90%。为了让该指标可验收，本章建议将精度拆解到不同输出对象。"
        "若评价可调容量预测，可采用容量预测误差不超过阈值的样本占比、平均绝对百分比误差和归一化均方根误差；若评价是否可调用，可采用准确率、召回率、精确率和F1值；"
        "若评价响应能力等级，可采用等级一致率和相邻等级误差率；若评价响应曲线，可采用跟踪误差、峰值误差、响应时延误差和持续时间误差。"
    ),
    (
        "p",
        "在报告阶段性表述中，不宜写成“模型已经达到90%精度”，除非已有真实验证集和统计结果。更稳妥的写法是：本课题以不低于90%作为模型建设目标，"
        "后续将基于真实调节事件数据，分别从容量预测准确性、可调用判断准确性、响应能力等级一致性和响应曲线跟踪误差四类口径开展验证。"
        "当真实数据不足时，可先采用仿真样本、历史负荷回放和小样本实测事件构建阶段性验证集，并明确样本范围和适用边界。"
    ),
    (
        "p",
        "精度评价还应按资源类型、市场场景和时间尺度分层报告。一个总体90%指标可能掩盖某类资源表现较差的问题，例如储能模型精度较高但工业负荷模型精度较低，"
        "日前场景精度较高但实时响应场景精度不足。因此，正式报告建议给出分资源、分场景、分时段的精度统计，并对低精度场景说明原因和后续优化措施。"
    ),
    ("h2", "4.10 模型输出、应用接口与真实数据替换口径"),
    (
        "p",
        "综合响应能力特征模型的输出应服务于后续资源智能分级分类和虚拟电厂市场化运营。建议输出字段包括资源编号、预测时刻、市场场景、向上可信容量、向下可信容量、可调电量、"
        "最大持续时间、最小响应时延、爬坡速率、跟踪精度、恢复时间、反弹风险、可用概率、意愿开放比例、历史可靠度、市场适配度、安全校核结果和主要限制因素。"
        "这些输出既可以进入第五章的分级分类模型，也可以直接服务于资源邀约、市场申报、组合优化和调度执行。"
    ),
    (
        "p",
        "后续真实数据进入后，本章应优先替换四类内容。第一，补充真实输入样例，展示资源主数据、状态时序、市场信号和调节事件如何形成模型样本；第二，补充分资源建模公式或参数，"
        "说明光伏、储能、充电站、工业负荷和楼宇空调的能力边界计算方法；第三，补充模型训练与验证结果，包括样本数量、训练/测试划分、误差统计和90%精度口径；第四，"
        "补充典型解释案例，说明模型如何识别某次资源能力受限的原因。"
    ),
    ("h2", "4.11 本章小结"),
    (
        "p",
        "本章提出了虚拟电厂资源可调容量与响应能力特征建模方法，核心思路是以基线预测为前提，以资源物理和业务边界为基础，以多维行为特征库为数据支撑，"
        "以主观意愿、历史可靠度、场景匹配和安全校核为修正，输出可用于市场申报和资源分类的可信能力向量。该方法将额定容量、理论容量、状态可用容量、可信可调用容量和市场有效容量"
        "逐层区分，有助于提高模型解释性和工程落地性。后续章节将在此基础上进一步开展面向多元市场调节需求的资源智能分级分类方法研究。"
    ),
]


REFERENCES = [
    "[1] International Energy Agency. Demand Response. https://www.iea.org/energy-system/energy-efficiency-and-demand/demand-response.",
    "[2] Riaz S, Mancarella P. On feasibility and flexibility operating regions of virtual power plants and TSO/DSO interfaces. arXiv:2107.05144.",
    "[3] Wang H, Wu J. Flexibility evaluation and stochastic optimization for virtual power plants with distributed energy resources. arXiv:2006.16170.",
    "[4] Luo Z, Hong T, Yin J, Piette M A. Building virtual power plant: Flexibility estimation and operation. arXiv:2004.05807.",
    "[5] Cui S, Wang Y W, Lin X K, Xiao J W. Grid-aware distributed energy resource aggregation and market participation in distribution networks. arXiv:2207.12685.",
    "[6] Federal Energy Regulatory Commission. Assessment of Demand Response and Advanced Metering. https://www.ferc.gov/industries-data/electric/power-sales-and-markets/demand-response/reports-demand-response-and-advanced-metering.",
    "[7] Recke N, Hudoba de Badyn M. Distributionally Robust Model Predictive Control for Virtual Power Plants. arXiv:2605.14642.",
    "[8] Oladimeji O, Ortega A, Sigrist L, Sanchez-Martin P, Lobato E, Rouco L. Modeling Demand Flexibility of RES-based Virtual Power Plants. arXiv:2112.03261.",
    "[9] Zhang Y, Liu F, Wang Z, Su Y, Wang W, Feng S. Robust Scheduling of Virtual Power Plant under Exogenous and Endogenous Uncertainties. arXiv:2101.10800.",
    "[10] OpenADR Alliance. OpenADR Primer and demand response event information model. https://www.openadr.org/.",
    "[11] Riaz S, Mancarella P. On Feasibility and Flexibility Operating Regions of Virtual Power Plants and TSO/DSO interfaces. arXiv:1906.05472.",
    "[12] Hashmi M U, Van Hertem D, van der Meer A, Keane A. Linear energy storage and flexibility model with ramp rate, ramping, deadline and capacity constraints. arXiv:2409.08084.",
    "[13] Lin W, Zhao C. AC-Feasible Power Transfer Regions of Virtual Power Plants: Characterization and Application. arXiv:2202.04456.",
    "[14] Wang X, Tang W. Analysis and Evaluation of Baseline Manipulation in Demand Response Programs. arXiv:2011.10681.",
    "[15] Muller F L, Jansen B. Large-Scale Demonstration of Precise Demand Response Provided by Residential Heating Systems. arXiv:1806.07670.",
]


def insert_paragraph_after(paragraph, text="", style=None):
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    new_para = Paragraph(new_p, paragraph._parent)
    if style:
        new_para.style = style
    if text:
        new_para.add_run(text)
    return new_para


def delete_paragraph(paragraph):
    element = paragraph._element
    element.getparent().remove(element)
    paragraph._p = paragraph._element = None


def set_east_asia_font(paragraph, font_name="宋体", size_pt=12):
    for run in paragraph.runs:
        run.font.name = font_name
        run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), font_name)
        if paragraph.style.name == "Normal":
            run.font.size = Pt(size_pt)


def replace_section(doc, start_prefix, end_prefix, content):
    start = None
    end = None
    for idx, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        style_name = para.style.name if para.style is not None else ""
        if style_name == "Heading 1" and text.startswith(start_prefix):
            start = idx
        elif start is not None and style_name == "Heading 1" and text.startswith(end_prefix):
            end = idx
            break
    if start is None or end is None:
        raise SystemExit(f"Could not locate section: {start_prefix}")
    section_heading = doc.paragraphs[start]
    for para in list(doc.paragraphs[start + 1 : end]):
        delete_paragraph(para)
    anchor = section_heading
    for kind, text in content:
        style = "Heading 2" if kind == "h2" else "Normal"
        anchor = insert_paragraph_after(anchor, text, style=style)
        set_east_asia_font(anchor)
        if kind == "p":
            anchor.paragraph_format.first_line_indent = Pt(24)
            anchor.paragraph_format.space_after = Pt(6)
            anchor.paragraph_format.line_spacing = 1.25


def replace_references(doc):
    ref_heading = None
    ref_index = None
    for idx, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        style_name = para.style.name if para.style is not None else ""
        if style_name == "Heading 1" and text == "参考文献":
            ref_heading = para
            ref_index = idx
            break
    if ref_heading is None:
        ref_heading = doc.add_paragraph("参考文献", style="Heading 1")
        ref_index = len(doc.paragraphs) - 1
    for para in list(doc.paragraphs[ref_index + 1 :]):
        delete_paragraph(para)
    anchor = ref_heading
    for ref in REFERENCES:
        anchor = insert_paragraph_after(anchor, ref, style="Normal")
        set_east_asia_font(anchor, size_pt=10.5)
        anchor.paragraph_format.first_line_indent = Pt(0)
        anchor.paragraph_format.space_after = Pt(3)
        anchor.paragraph_format.line_spacing = 1.15


def main():
    source = REPORTS_DIR / SOURCE_NAME
    output = REPORTS_DIR / OUTPUT_NAME
    if not source.exists():
        raise SystemExit(f"Source not found: {source}")
    doc = Document(source)
    replace_section(
        doc,
        "4 虚拟电厂资源可调容量与响应能力特征建模方法研究",
        "5 面向多元市场调节需求的资源智能分级分类方法研究",
        SECTION_4_CONTENT,
    )
    replace_references(doc)
    doc.save(output)
    print(output)


if __name__ == "__main__":
    main()
