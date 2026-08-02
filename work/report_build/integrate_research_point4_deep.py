from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.text.paragraph import Paragraph


REPORTS_DIR = Path("outputs/reports")
SOURCE_NAME = "技术报告-课题一-虚拟电厂多元异质资源调节行为分析与智能分类方法-第三版-研究点一二三深度扩写版.docx"
OUTPUT_NAME = "技术报告-课题一-虚拟电厂多元异质资源调节行为分析与智能分类方法-第三版-研究点一二三四深度扩写版.docx"


SECTION_5_CONTENT = [
    ("h2", "5.1 研究定位与分类目标"),
    (
        "p",
        "面向多元市场调节需求的资源智能分级分类方法，是将前述资源行为影响因素、调节意愿、动态能力和可信可调用容量转化为市场运营决策的关键环节。"
        "虚拟电厂聚合的资源类型复杂，单纯按照“光伏、储能、充电桩、工业负荷、楼宇空调”等物理类型分类，无法回答资源适合参与哪类市场、应作为主力资源还是备用资源、"
        "是否适合自动调用、是否需要组合调用等运营问题。因此，本章的分类目标不是给资源贴静态标签，而是根据多元市场任务要求和资源动态能力画像，形成可随时间、状态和市场场景更新的能力等级与市场适配分类。"
    ),
    (
        "p",
        "本研究建议将资源分类结果分为两个层次：一是通用能力等级，用于描述资源在容量、速度、持续时间、精度、可靠度、经济性和开放意愿等维度上的综合能力；"
        "二是市场适配类别，用于描述资源适合参与现货移峰、需求响应、备用、调频、绿电消纳或碳减排协同等具体场景的程度。"
        "前者回答“资源本身能力强不强”，后者回答“资源适不适合某个市场任务”。两者结合，才能避免出现“综合能力高但场景不匹配”或“单项能力突出但被整体评分淹没”的问题。"
    ),
    (
        "p",
        "从技术路线看，本章采用“市场需求画像、资源能力画像、规则基准分级、数据驱动分类、约束校核、闭环更新”的方法。市场需求画像定义不同市场对容量、速度、持续时间和可靠度的要求；"
        "资源能力画像来自第四章模型输出；规则基准分级用于形成可解释初始结果；数据驱动分类用于从历史运行曲线和调节事件中发现资源行为模式；约束校核用于保证分类结果能实际落地；"
        "闭环更新则根据市场执行结果不断修正等级和分类边界。"
    ),
    ("h2", "5.2 多元市场调节需求画像"),
    (
        "p",
        "资源分级分类必须从市场需求出发。不同市场对资源能力的要求差异明显：现货或分时价格响应更关注可调电量、持续时间、价格弹性和调节成本；"
        "需求响应更关注基线可核验性、通知提前量、完成比例、用户参与稳定性和反弹风险；备用服务更关注可用概率、持续保持能力、启动时间和失败风险；"
        "调频或快速调节服务更关注响应时延、爬坡速率、跟踪精度和高频动作能力；绿电消纳和碳协同场景则更关注绿色属性、可转移负荷窗口和与新能源出力的匹配程度。"
    ),
    (
        "p",
        "因此，本研究建议将每类市场任务抽象为需求向量M_m=[P_req,E_req,T_req,tau_req,ramp_req,acc_req,rel_req,cost_req,green_req]。"
        "其中P_req表示功率规模要求，E_req表示能量要求，T_req表示持续时间要求，tau_req表示响应时延要求，ramp_req表示爬坡要求，acc_req表示调节精度要求，"
        "rel_req表示可靠度要求，cost_req表示成本约束，green_req表示绿色属性或消纳协同要求。不同市场的权重不同，不能用统一权重评价所有资源。"
    ),
    (
        "p",
        "外部研究也表明，分布式资源聚合参与市场需要同时考虑资源约束、网络约束和市场产品要求。FERC Order 2222 推动分布式资源聚合参与批发市场，"
        "相关研究进一步指出，聚合灵活资源参与市场时需要形成可申报的成本曲线或能力边界，并进行配电网约束校核[16][17]。这些研究启示本课题：资源分类不能只做静态能力评分，"
        "还要面向不同市场产品定义适配边界。"
    ),
    ("h2", "5.3 资源能力画像与分类特征体系"),
    (
        "p",
        "资源能力画像应继承第四章的模型输出，并进一步组织成分类特征。基础能力特征包括额定功率、可信向上/向下容量、可调电量、最大持续时间、响应时延、爬坡速率、调节精度、恢复时间和反弹风险；"
        "行为特征包括近30日参与率、能力开放比例、近30日任务成功率、近30日平均偏差、近7日调度次数、疲劳指数和历史可靠度；经济特征包括补偿敏感度、调节成本、机会成本、违约风险和结算收益；"
        "场景特征包括市场类型、调节方向、价格/补偿信号、开始结束时间、目标功率和目标持续时间。"
    ),
    (
        "p",
        "项目数据字典中的behavior_feature表已经为分类模型提供了重要字段基础，例如participation_rate_30d、capability_open_ratio、success_rate_30d、"
        "avg_deviation_30d、dispatch_count_7d、fatigue_index、history_reliability和estimated_dynamic_capacity_kw等。"
        "这些字段可以直接用于构建资源能力指标宽表。market_signal、regulation_event和regulation_result表则可提供市场场景、目标功率、实际调节量、完成比例、响应时间和调节精度，"
        "用于训练和验证市场适配分类。"
    ),
    (
        "p",
        "分类特征体系应坚持“少用不可解释黑箱特征、多保留可运营解释”的原则。对于评审和工程应用而言，模型给出某资源属于“快速高精度型”或“长时低成本型”并不够，"
        "还应说明分类原因，例如响应时延短、历史可靠度高、持续时间不足、疲劳指数偏高、用户开放比例低或市场适配度受限。"
        "这类解释可直接转化为资源运营动作，如提升授权等级、优化激励、调整调用频次或与其他资源组合。"
    ),
    ("h2", "5.4 分级规则与等级体系设计"),
    (
        "p",
        "在真实样本不足的阶段，建议先建立可解释的规则基准等级，作为智能分类模型的起点和校验对象。通用能力等级可分为A、B、C、D四级："
        "A级表示容量、速度、持续时间、可靠度和开放意愿均较好，可作为优先调用资源；B级表示多数指标满足要求，但存在某一维度短板，适合作为常规可调用资源；"
        "C级表示资源具备一定调节潜力，但受状态、用户意愿或可靠度约束较大，适合作为补充或低频调用资源；D级表示当前不可调用或仅可观察，需等待状态改善、授权提升或数据补齐。"
    ),
    (
        "p",
        "市场适配等级应按场景分别定义。例如，调频适配等级重点看响应时延、爬坡速率、跟踪精度和通信控制可达性；现货移峰适配等级重点看可调电量、持续时间、价格弹性和恢复反弹；"
        "备用适配等级重点看可用概率、持续保持时间和历史可靠度；需求响应适配等级重点看基线可核验性、用户参与稳定性、完成比例和退出风险；"
        "绿电消纳适配等级重点看负荷可转移窗口与新能源出力高峰的匹配程度。这样可以形成“一资源多标签”的分类结果，而不是把资源强行归入单一类别。"
    ),
    (
        "p",
        "规则基准可以采用阈值法、加权评分法或多准则决策法。阈值法适合关键硬约束，如响应时延超过市场要求则不进入调频候选池；加权评分法适合形成综合等级；"
        "TOPSIS、AHP或熵权法等多准则方法适合在数据不足但专家经验明确时构建初始排序。规则基准不应作为最终模型，而应作为后续机器学习分类的解释参照和质量底线。"
    ),
    ("h2", "5.5 智能分类模型方法"),
    (
        "p",
        "在样本逐步积累后，可引入数据驱动分类方法。第一类是无监督聚类，用于发现资源自然分组，例如快速响应型、长时持续型、高可靠低容量型、高容量低频型、价格敏感型和舒适约束型。"
        "可选方法包括K-means、层次聚类、高斯混合模型和密度聚类。聚类输入可包括能力向量、历史响应曲线特征、市场场景特征和用户行为特征，输出用于形成资源行为类别。"
    ),
    (
        "p",
        "第二类是半监督或监督分类。当已有人工规则等级、专家标注或历史市场适配结果时，可训练分类模型预测资源在不同市场场景下的适配等级。"
        "可选方法包括逻辑回归、随机森林、梯度提升树、支持向量机和轻量神经网络。对于技术报告阶段，建议优先采用可解释性较好的模型作为主模型，并将复杂模型作为精度提升或特征提取模块，"
        "避免分类结果难以解释。"
    ),
    (
        "p",
        "第三类是自监督表征学习。由于虚拟电厂真实标注样本往往不足，但运行曲线、调节事件和市场信号序列较多，可利用自监督学习从资源时序数据中学习行为表示。"
        "例如，可通过遮蔽预测、序列重构、相似事件对比学习等方式学习资源在不同状态下的响应模式，再将学习到的表示用于聚类或下游分类。"
        "这种方法适合解决“标签少、时序多、资源异质性强”的问题，但需要在报告中说明其只是后续深化方向，当前阶段可先以规则基准和可解释模型为主。"
    ),
    ("h2", "5.6 市场适配度计算与资源池构建"),
    (
        "p",
        "资源分类的直接应用是构建面向不同市场的候选资源池。对于市场m，可将资源i的市场适配度表示为S_i,m=Match(F_i,M_m) x R_i x W_i x Safe_i。"
        "其中F_i为资源能力特征向量，M_m为市场需求向量，R_i为历史可靠度，W_i为意愿开放程度，Safe_i为安全校核结果。"
        "Match函数可根据不同市场设置权重，也可通过历史执行结果学习得到。"
    ),
    (
        "p",
        "在资源池构建上，建议形成分层候选池。一级资源池为优先调用资源，要求市场适配度高、历史可靠度高、控制可达性好；二级资源池为补充调用资源，"
        "可在容量不足或价格较优时调用；三级资源池为备用观察资源，具备潜力但当前状态或历史可靠度不足；剔除资源池为不满足硬约束或安全校核失败的资源。"
        "这种资源池结构比单一排序更适合实际运营，因为虚拟电厂通常需要在收益、风险和履约之间平衡。"
    ),
    (
        "p",
        "资源池还应支持组合调用。某些资源单独看并不适合某一市场，但与其他资源组合后可能形成可用能力。例如，光伏预测偏差可由储能平滑，空调负荷可提供短时削峰，"
        "工业负荷可提供较大容量但不适合高频调用，充电站可作为中短时可移峰资源。智能分类模型应不仅输出单资源类别，还应支持“主力资源、补偿资源、备用资源、缓冲资源”的组合角色识别。"
    ),
    ("h2", "5.7 约束校核与分类结果修正"),
    (
        "p",
        "市场适配分类必须经过约束校核。约束校核包括资源状态校核、用户授权校核、设备安全校核、通信控制校核、市场规则校核和配电网安全校核。"
        "例如，储能即使被分类为快速响应型资源，如果SOC接近边界，也应在当前时段降级；充电站即使适合现货移峰，如果大量车辆即将离站，也不应参与长时调用；"
        "楼宇空调即使具备短时削减能力，如果室内温度已接近舒适边界，应降低适配等级；工业负荷即使容量较大，如果处于关键生产工序，应退出候选资源池。"
    ),
    (
        "p",
        "分类结果应区分长期标签和短期状态。长期标签描述资源相对稳定的能力属性，例如“高可靠储能”“长时工业柔性负荷”“短时空调削减资源”；"
        "短期状态描述某一时刻能否参与某市场，例如“当前SOC不足”“当前疲劳指数偏高”“当前用户未授权”“当前市场任务不匹配”。"
        "报告中应避免将短期不可调用误写成资源长期能力差，也应避免将长期能力强的资源在任何时刻都视为可调用。"
    ),
    (
        "p",
        "约束校核后的结果可形成分类修正机制：若资源通过硬约束但部分软指标不足，可保持类别但降低优先级；若资源违反硬约束，则直接移出当前市场资源池；"
        "若资源连续多次履约优良，则提高历史可靠度并提升优先级；若资源连续出现偏差、退出或反弹超限，则降低等级或要求人工复核。"
    ),
    ("h2", "5.8 分类效果验证与评价指标"),
    (
        "p",
        "智能分级分类模型的验证不能只看聚类指标或分类准确率，还要看市场运营效果。模型层面可采用轮廓系数、Calinski-Harabasz指数、Davies-Bouldin指数评价聚类区分度，"
        "采用准确率、召回率、F1值、等级一致率和相邻等级误差率评价分类结果。业务层面则应评价分类后资源调用成功率、响应偏差、履约考核、调用成本、资源疲劳度和市场收益变化。"
    ),
    (
        "p",
        "对于“模型精度不低于90%”的项目要求，第五章建议与第四章保持一致，明确分类模型可采用多口径评价：若评价市场适配判断，可用适配命中率或可调用判断准确率；"
        "若评价等级分类，可用等级一致率或相邻等级误差率；若评价资源池构建效果，可用入池资源实际完成率、容量覆盖率和违约率；若评价综合运营效果，可用市场回放中收益提升和偏差降低。"
        "在真实数据不足时，应写成验证方案，不提前声称已达到90%。"
    ),
    (
        "p",
        "场景回放是验证资源分类价值的重要方法。可选择典型高峰削减、低谷消纳、备用调用、快速响应和绿电消纳场景，用历史价格、气象、负荷和资源状态数据回放分类结果，"
        "比较智能分类资源池与传统按资源类型筛选、按额定容量排序或人工经验筛选之间的差异。若智能分类能够提高完成率、降低偏差、降低调用成本或减少用户退出，即可说明其工程价值。"
    ),
    ("h2", "5.9 真实数据支撑与后续替换口径"),
    (
        "p",
        "后续真实数据进入后，本章应优先补充五类材料。第一，补充市场需求向量样例，明确现货、需求响应、备用、调频和绿电消纳等场景的指标要求和权重；"
        "第二，补充资源能力画像样例，展示不同资源的容量、速度、持续时间、可靠度、意愿和成本特征；第三，补充规则基准等级，说明A/B/C/D等级或市场适配等级如何由阈值和权重生成；"
        "第四，补充智能分类模型结果，包括聚类类别、分类准确性、等级稳定性和解释变量；第五，补充市场回放结果，展示分类前后资源调用效果差异。"
    ),
    (
        "p",
        "真实数据表述应避免只给出最终分类标签，而应同时给出标签依据。例如，某储能资源被归为“调频优先资源”，应说明其响应时延、爬坡速率、跟踪精度、SOC管理和历史可靠度均满足要求；"
        "某充电站被归为“现货移峰补充资源”，应说明其在线车辆波动较大但中短时移峰价值较高；某工业负荷被归为“长时备用资源”，应说明其容量大、持续时间长但调用频率受限。"
        "这样后续评审人员更容易理解分类结果的技术依据。"
    ),
    ("h2", "5.10 本章小结"),
    (
        "p",
        "本章提出面向多元市场调节需求的资源智能分级分类方法，核心是将市场需求画像与资源能力画像进行匹配，并通过规则基准、数据驱动分类、约束校核和闭环反馈形成可运营的资源等级与市场适配类别。"
        "该方法既保留了规则分级的可解释性，也为后续引入聚类、半监督分类和自监督表征学习预留空间。其输出可直接服务于虚拟电厂资源池构建、市场申报、组合调用和履约风险控制，"
        "并与前文可调容量和响应能力特征模型共同支撑课题一“多元异质资源调节行为分析与智能分类方法”的完整技术链条。"
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
    "[16] Federal Energy Regulatory Commission. Order No. 2222: Participation of Distributed Energy Resource Aggregations in Markets Operated by Regional Transmission Organizations and Independent System Operators. https://www.ferc.gov/.",
    "[17] Cui B, Zamzam A, Bernstein A. Enabling Grid-Aware Market Participation of Aggregate Flexible Resources. arXiv:2207.12685.",
    "[18] Oladimeji O, Ortega A, Sigrist L, Rouco L, Sanchez-Martin P, Lobato E. Optimal Participation of Heterogeneous, RES-based Virtual Power Plants in Energy Markets. arXiv:2112.02200.",
    "[19] Zapparoli L, Gjorgjev B, Sansavini G. Optimal Duration of Reserve Capacity Ancillary Services for Distributed Energy Resources. arXiv:2504.06729.",
    "[20] Muller F L, Szabo J, Sundstrom O, Lygeros J. Aggregation and Disaggregation of Energetic Flexibility from Distributed Energy Resources. arXiv:1705.02815.",
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
        "5 面向多元市场调节需求的资源智能分级分类方法研究",
        "6 多维行为特征库构建与数据治理方案",
        SECTION_5_CONTENT,
    )
    replace_references(doc)
    doc.save(output)
    print(output)


if __name__ == "__main__":
    main()
