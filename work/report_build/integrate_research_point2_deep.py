from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.text.paragraph import Paragraph


REPORTS_DIR = Path("outputs/reports")
SOURCE_NAME = "技术报告-课题一-虚拟电厂多元异质资源调节行为分析与智能分类方法-第三版-研究点一深度扩写版.docx"
OUTPUT_NAME = "技术报告-课题一-虚拟电厂多元异质资源调节行为分析与智能分类方法-第三版-研究点一二深度扩写版.docx"


SECTION_3_CONTENT = [
    ("h2", "3.1 研究任务与问题界定"),
    (
        "p",
        "虚拟电厂资源调节意愿与动态调节能力影响机理模型研究，是将第二章“影响因素清单”转化为可解释、可计算、可验证模型的关键环节。"
        "在虚拟电厂运营中，资源未达到预期响应并不一定意味着资源没有调节潜力，可能是用户不愿意开放能力，也可能是资源当前状态不满足调节要求，"
        "还可能是资源具备能力但不匹配具体市场任务的速度、持续时间、精度或安全约束。因此，本章的核心任务是把资源响应行为拆解为“调节意愿、动态调节能力、"
        "场景匹配、历史可靠度、安全校核”五个相互关联的状态变量，建立从影响因素到可信可调用能力的机理链条。"
    ),
    (
        "p",
        "与传统基于额定容量或历史最大响应量的评估方式不同，本研究强调资源能力的时变性和行为性。额定容量只能描述资源的物理上限，不能说明某一时刻是否可用；"
        "历史最大响应量只能说明曾经达到过的水平，不能保证未来在不同市场信号、不同天气、不同用户业务状态下仍然可复现。需求响应和虚拟电厂相关研究普遍强调，"
        "用户侧资源响应取决于价格或激励信号、运行状态、外部环境、用户授权和执行控制等多重因素[1][6]。因此，本章不把“低响应”简单归因于单一原因，"
        "而是建立可分解的原因识别框架，为后续模型诊断和运营优化提供依据。"
    ),
    (
        "p",
        "本章所说的调节意愿，是资源所有者或运营主体在特定市场场景下愿意参与调节、愿意开放容量、愿意持续响应的综合行为倾向；动态调节能力，"
        "是资源在某一时刻受物理属性、实时状态、外部环境和业务安全边界共同约束后能够实际提供的功率、电量、时间和可靠性边界。二者不能互相替代："
        "用户非常愿意参与但车辆即将离站、储能SOC不足或工业产线处于关键工序时，无法形成有效响应；设备具备能力但用户未授权、收益不足或担心业务影响时，"
        "也不能直接纳入市场可交易能力。"
    ),
    ("h2", "3.2 调节意愿的潜变量结构"),
    (
        "p",
        "调节意愿具有明显的潜变量特征，不能像功率、电量、SOC那样被设备直接量测。本研究建议将调节意愿拆分为三个可解释维度：参与概率、能力开放比例和持续参与概率。"
        "参与概率回答资源是否接受当前调节任务；能力开放比例回答资源愿意把多少理论能力交由虚拟电厂调用；持续参与概率回答资源在任务执行期间是否保持授权、不中途退出。"
        "这三个维度共同决定资源从“潜在可调”转化为“可开放调节”的程度。"
    ),
    (
        "p",
        "调节意愿的形成机制可以概括为净收益驱动、风险约束、任务属性影响、用户偏好修正和历史反馈更新。净收益驱动包括市场补偿、节省电费、结算收益和机会成本；"
        "风险约束包括生产损失、舒适度投诉、出行不便、电池寿命损耗和偏差考核；任务属性包括通知提前量、响应方向、持续时间、调用频率、是否允许人工确认以及是否允许自动控制；"
        "用户偏好则体现为价格敏感度、风险厌恶程度、绿色价值取向、对平台信任程度和授权习惯。历史反馈会改变用户对下一次任务的预期：一次收益清晰、扰动较小、结算顺畅的响应，"
        "通常会提高后续参与概率；一次收益不明确、考核偏严或业务受影响的响应，则可能降低后续意愿。"
    ),
    (
        "p",
        "在无直接问卷或偏好调查数据的阶段，调节意愿可以通过行为代理变量进行间接估计。例如，接受邀约率、申报容量比例、授权等级、中途退出次数、响应前人工确认时长、"
        "历史参与频次和结算后继续参与率，均可作为意愿状态的外部表现。但需要注意，低响应量不能直接等同于低意愿，因为同一结果也可能由客观能力不足造成。"
        "因此，意愿模型必须与能力模型联合解释，避免把设备状态问题误判为用户态度问题，也避免把用户拒绝问题误判为技术调控问题。"
    ),
    ("h2", "3.3 调节意愿模型表达"),
    (
        "p",
        "调节意愿模型可采用分层离散选择或广义线性混合模型进行表达。对于资源i在时刻t、市场场景m下的参与概率，可用W_part,i(t,m)表示；"
        "对于愿意开放的容量比例，可用W_open,i(t,m)表示；对于任务期间保持参与的概率，可用W_keep,i(t,m)表示。概念上，调节意愿可表示为："
        "W_i(t,m)=F(B_i(t,m)-K_i(t,m), Risk_i(t,m), Task_m, Pref_i, State_i(t), H_i(t))。其中，B表示预计收益，K表示机会成本和不便成本，"
        "Risk表示风险感知，Task表示调节任务属性，Pref表示用户偏好，State表示当前业务或用能状态，H表示历史参与反馈。"
    ),
    (
        "p",
        "若后续获得较完整的响应事件数据，参与概率可采用Logit或Probit模型刻画，能力开放比例可采用Beta回归、分段回归或有界回归模型刻画，持续参与概率可采用生存分析或"
        "事件退出模型刻画。若资源主体差异明显，例如工业用户、商业楼宇、充电站和储能运营商之间存在不同偏好，可引入资源类型或用户主体的随机效应，形成分层模型。"
        "若数据量不足，则可先采用专家规则与小样本校准结合的方式，给出意愿等级和参数初值，待真实数据积累后再进行统计估计。"
    ),
    (
        "p",
        "调节意愿模型的输出不应只是一个抽象分数，而应服务于运营决策。建议输出“是否建议邀约、建议邀约容量、是否需要人工确认、是否适合自动控制、预期退出风险、"
        "影响意愿的主要原因”等结果。这样，模型既可以支持资源筛选，也可以反向指导运营策略，例如对价格敏感型用户优化激励，对风险敏感型用户优化保障条款，"
        "对授权不足用户优化合同和控制权限设计。"
    ),
    ("h2", "3.4 动态调节能力的能力向量结构"),
    (
        "p",
        "动态调节能力是资源在特定时刻的实际可用边界，不能简化为单一功率值。对于虚拟电厂而言，真正有用的能力应以向量形式表达，包括上调功率、下调功率、可调电量、"
        "最大持续时间、最小响应时间、爬坡速率、恢复时间、调节精度、可用概率和反弹风险。不同市场任务会调用能力向量中的不同分量：现货移峰更关注电量和持续时间，"
        "辅助服务更关注响应速度和跟踪精度，备用场景更关注可用概率和持续保持能力，需求响应场景则更关注基线可核验性、完成比例和响应后的恢复影响。"
    ),
    (
        "p",
        "动态能力由理论能力边界和可信能力边界两层构成。理论能力边界由设备物理参数和业务安全约束决定，例如储能的额定功率、容量、SOC上下限和充放电效率，"
        "充电站的站内容量、在线车辆、目标电量和离站时间，工业负荷的工艺约束和可移峰窗口，楼宇空调的舒适温度边界和建筑热惯性。可信能力边界则在理论边界基础上，"
        "进一步考虑预测误差、通信可靠性、历史响应偏差、环境不确定性和安全冗余。相关虚拟电厂灵活性研究也将资源运行约束和不确定性纳入可用灵活性范围，"
        "而不是仅采用确定性最大容量[2][7]。"
    ),
    (
        "p",
        "从工程实现看，能力向量可以表示为C_i(t)=[P_up,i(t), P_down,i(t), E_i(t), T_i(t), R_i(t), Acc_i(t), Rec_i(t), Prob_i(t)]。"
        "其中P_up和P_down表示上下调功率边界，E表示可调电量，T表示可持续时间，R表示爬坡或响应速度，Acc表示调节精度，Rec表示恢复时间或反弹风险，"
        "Prob表示在当前状态和不确定性条件下的可用概率。该表达既保留了资源物理含义，也便于后续与市场场景进行匹配。"
    ),
    ("h2", "3.5 典型资源动态能力形成机理"),
    (
        "p",
        "分布式光伏的动态能力主要受气象条件、当前出力、预测误差、并网约束和是否配置储能影响。单体光伏通常更容易提供向下调节，即通过限发或逆变器控制降低出力；"
        "向上调节通常依赖前期存在限发基线、配套储能释放或与负荷侧资源组合实现。光伏资源的动态能力应重点刻画预测出力、实际出力、可控弃光空间、短时波动风险和"
        "与储能/负荷协同后的组合调节能力。"
    ),
    (
        "p",
        "储能资源的动态能力相对清晰，但不能只看额定功率。SOC决定当前可充可放空间，SOH和温度影响安全边界，循环寿命成本影响可持续调用策略，后续计划SOC轨迹影响"
        "是否需要预留容量。储能在调频、备用和现货套利场景中的能力表达也不同：调频更关注快速跟踪和高频动作损耗，备用更关注容量预留和可用率，现货套利更关注"
        "价格价差、效率损失和充放电时序。"
    ),
    (
        "p",
        "充电桩及充电站的动态能力来自车辆群体聚合，其核心不确定性在于车辆到站、离站和用户目标电量。站内某一时刻的总充电功率并不等于可调能力，"
        "因为部分车辆可能即将离站，部分车辆可能已接近目标电量，部分用户可能不允许降低充电速度。若考虑V2G，还需计入放电授权、电池损耗认知、双向充放电设备能力和"
        "车辆可用时长。充电资源能力模型应重点刻画在线车辆集合、剩余停车时间、当前SOC、目标SOC、最小保障电量和用户授权等级。"
    ),
    (
        "p",
        "工业负荷的动态能力与生产工艺深度相关。对连续型生产负荷而言，主工艺负荷可调空间通常有限，但辅助系统可能具备短时调节能力；对批处理、冷链、空压、泵类和"
        "可排程设备而言，负荷转移空间更大。工业资源能力模型应把生产阶段、工艺安全边界、订单交付、库存缓冲、设备启停成本和恢复时间纳入约束，避免简单依据"
        "历史负荷波动推断可调能力。"
    ),
    (
        "p",
        "商业楼宇和空调负荷的动态能力与建筑热惯性、室内外温差、人员密度和舒适度边界相关。短时调节可以通过调整设定温度、预冷预热、削减新风或优化群控策略实现；"
        "但响应结束后可能出现反弹负荷，且舒适度投诉会反向影响用户后续参与意愿。因此，楼宇能力模型应同时估计可削减功率、可持续时间、舒适度风险和反弹风险。"
    ),
    ("h2", "3.6 意愿与能力耦合机理"),
    (
        "p",
        "调节意愿与动态调节能力不是简单并列关系，而是共同决定实际可信可调用能力。能力是物理基础，没有客观能力时，提高补偿也不能形成实际响应；"
        "意愿是开放条件，设备具备能力但用户未授权时，能力不能被市场调用；场景匹配是交易条件，意愿和能力均存在但无法满足某类市场的速度、持续时间或精度要求时，"
        "也不能计入该市场的可交易能力。"
    ),
    (
        "p",
        "本研究建议将资源i在时刻t、市场场景m下的可信可调用能力表示为：A_i(t,m)=C_i(t) x W_open,i(t,m) x Q_match,i(t,m) x R_history,i(t) x S_safe,i(t)。"
        "其中，C_i(t)为动态能力向量，W_open表示意愿开放比例，Q_match表示资源能力与市场任务要求的匹配程度，R_history表示历史可靠度修正，"
        "S_safe表示设备、电网和业务安全校核结果。该表达不是最终固定算法，而是阶段性机理模型，用于明确变量关系、数据需求和后续建模方向。"
    ),
    (
        "p",
        "在实际应用中，上式可进一步扩展为资源组合层面的可信能力。单资源能力具有随机性和脆弱性，资源组合可以通过互补性降低不确定性。例如，储能可弥补光伏预测偏差，"
        "楼宇空调可提供短时削峰，工业负荷可提供较大容量但低频调用，充电站可通过站群聚合平滑车辆随机性。组合能力不是单体能力的简单相加，还需要考虑同时可用性、"
        "空间约束、通信链路、控制策略和市场申报规则。"
    ),
    ("h2", "3.7 实际响应与闭环反馈机制"),
    (
        "p",
        "实际响应行为由可信可调用能力、调节指令、通信状态、控制执行和随机扰动共同决定。响应完成后，系统应将结果反馈到意愿模型、能力模型和可靠度模型中，"
        "形成闭环更新。若某资源多次出现响应延迟、持续时间不足或反弹明显，应降低其历史可靠度；若某资源在相似场景下稳定履约，则可提高其可信能力权重。"
        "这种闭环机制能够使模型从一次性评估转向持续学习。"
    ),
    (
        "p",
        "反馈机制至少包括四类信息。第一是收益反馈，实际净收益、结算周期和补偿透明度会改变用户后续参与意愿；第二是考核反馈，响应偏差、违约费用和考核豁免情况会改变风险感知；"
        "第三是状态反馈，储能SOC变化、电池寿命消耗、楼宇温度漂移、车辆目标电量完成情况会影响后续动态能力；第四是体验反馈，生产扰动、客户投诉、出行影响和人工干预成本"
        "会改变后续授权范围。上述反馈应进入多维行为特征库，作为后续模型迭代的重要数据资产。"
    ),
    (
        "p",
        "对于持续运营的虚拟电厂，闭环反馈比单次建模更重要。市场环境、用户行为和资源状态都会变化，若模型长期不更新，将出现意愿参数失真、能力边界过时和可靠度评价滞后。"
        "因此，本课题建议建立按事件更新和按周期更新相结合的机制：调节事件结束后立即更新履约特征，按周或按月更新用户偏好和资源可靠度，按季或按市场规则变化更新模型结构和参数。"
    ),
    ("h2", "3.8 模型验证与精度评价衔接"),
    (
        "p",
        "本章模型是后续“可调容量与响应能力特征模型精度不低于90%”要求的重要基础。需要强调的是，90%精度不应只理解为单一分类准确率，而应结合模型输出对象设定评价口径。"
        "如果输出对象是可调容量预测，可采用平均绝对百分比误差、归一化均方根误差或考核窗口内完成率；如果输出对象是是否可调用，可采用准确率、召回率、精确率和F1值；"
        "如果输出对象是能力等级，可采用等级一致率、相邻等级误差率和加权Kappa系数；如果输出对象是响应曲线，可采用跟踪误差、峰值误差、延迟误差和持续时间误差。"
    ),
    (
        "p",
        "为了验证意愿与能力耦合机理，应将低响应原因进行标签化。典型失败原因包括用户拒绝或未授权、当前状态不可用、市场任务不匹配、通信或控制失败、基线偏差过大、"
        "响应后反弹超过阈值、设备或业务安全约束触发等。通过对失败原因的分类统计，可以检验模型是否真正区分了“意愿不足”和“能力不足”，并为资源运营改进提供方向。"
        "若真实标签不足，可先采用专家标注、小样本事件复核和仿真事件构造相结合的方式建立阶段性验证集。"
    ),
    ("h2", "3.9 真实数据支撑与后续替换口径"),
    (
        "p",
        "后续若获取真实数据，本章应优先补充调节事件级数据、资源状态数据、用户授权数据和结算考核数据。调节事件级数据包括event_id、市场类型、指令下发时间、目标功率、"
        "基线功率、实际功率、响应开始时间、达到目标时间、持续时间、退出时间和恢复过程；资源状态数据包括SOC、在线车辆数、室内外温度、产线状态、设备运行状态、"
        "预测出力和实际出力；用户授权数据包括授权等级、人工确认结果、拒绝原因、可调用时段和容量上限；结算考核数据包括实际收益、补偿金额、偏差费用和违约记录。"
    ),
    (
        "p",
        "真实数据进入报告后，建议用三类结果替换当前框架性描述。第一类是模型变量显著性或贡献度结果，用于说明哪些因素最影响调节意愿和动态能力；第二类是典型资源案例，"
        "展示同一资源在不同状态和市场任务下的能力变化；第三类是模型验证结果，展示意愿预测、能力预测、可信可调用能力评估与实际响应之间的一致性。"
        "在数据尚不完整的阶段，可明确写成“模型框架验证方案”，不将阶段性假设表述为已经通过真实运行验证的结论。"
    ),
    ("h2", "3.10 本章小结"),
    (
        "p",
        "本章围绕虚拟电厂资源调节意愿与动态调节能力影响机理，构建了从潜在意愿、能力向量、场景匹配、历史可靠度到可信可调用能力的模型框架。"
        "该框架的价值在于将资源响应不足的原因拆解为可诊断、可建模、可运营优化的多个环节，避免用单一额定容量或历史响应量替代复杂的资源行为。"
        "本章成果将向第四章传递可调容量和响应能力特征建模所需的核心变量、能力向量和可信能力表达方式，也将为第五章资源智能分级分类提供意愿、能力、可靠度和市场适配维度的模型基础。"
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
        "3 虚拟电厂资源调节意愿与动态调节能力影响机理模型研究",
        "4 虚拟电厂资源可调容量与响应能力特征建模方法研究",
        SECTION_3_CONTENT,
    )
    replace_references(doc)
    doc.save(output)
    print(output)


if __name__ == "__main__":
    main()
