from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "reports" / "技术报告-课题一-虚拟电厂多元异质资源调节行为分析与智能分类方法-初稿.docx"


TITLE = "技术报告-课题一-虚拟电厂多元异质资源调节行为分析与智能分类方法"


def set_east_asia_font(run, font_name="宋体"):
    run.font.name = font_name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font_name)


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_cell_text(cell, text, bold=False):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if bold else WD_ALIGN_PARAGRAPH.LEFT
    r = p.add_run(text)
    set_east_asia_font(r)
    r.font.size = Pt(9.5)
    r.bold = bold
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER


def add_table(doc, headers, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        set_cell_text(hdr[i], h, bold=True)
        set_cell_shading(hdr[i], "F2F4F7")
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            set_cell_text(cells[i], str(value))
    if widths:
        for row in table.rows:
            for idx, width in enumerate(widths):
                row.cells[idx].width = Cm(width)
    doc.add_paragraph()
    return table


def add_para(doc, text="", style=None, bold_prefix=None):
    p = doc.add_paragraph(style=style)
    if bold_prefix and text.startswith(bold_prefix):
        r1 = p.add_run(bold_prefix)
        set_east_asia_font(r1)
        r1.bold = True
        r2 = p.add_run(text[len(bold_prefix):])
        set_east_asia_font(r2)
    else:
        r = p.add_run(text)
        set_east_asia_font(r)
    return p


def add_bullets(doc, items):
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        r = p.add_run(item)
        set_east_asia_font(r)


def add_numbered(doc, items):
    for item in items:
        p = doc.add_paragraph(style="List Number")
        r = p.add_run(item)
        set_east_asia_font(r)


def add_data_note(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.3)
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run("真实数据支撑与后续替换口径：")
    set_east_asia_font(r)
    r.bold = True
    r.font.color.rgb = RGBColor(31, 77, 120)
    r2 = p.add_run(text)
    set_east_asia_font(r2)
    return p


def add_caption(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    set_east_asia_font(r)
    r.font.size = Pt(9)
    r.font.color.rgb = RGBColor(89, 89, 89)
    return p


def configure_styles(doc):
    section = doc.sections[0]
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    section.header_distance = Inches(0.492)
    section.footer_distance = Inches(0.492)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "宋体"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    normal.font.size = Pt(11)
    normal.paragraph_format.line_spacing = 1.10
    normal.paragraph_format.space_after = Pt(6)

    for name, size, color, before, after in [
        ("Heading 1", 16, "2E74B5", 16, 8),
        ("Heading 2", 13, "2E74B5", 12, 6),
        ("Heading 3", 12, "1F4D78", 8, 4),
    ]:
        style = styles[name]
        style.font.name = "宋体"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor.from_string(color)
        style.font.bold = True
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)

    for name in ["List Bullet", "List Number"]:
        style = styles[name]
        style.font.name = "宋体"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
        style.font.size = Pt(11)
        style.paragraph_format.space_after = Pt(4)

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = footer.add_run("课题一技术报告初稿")
    set_east_asia_font(r)
    r.font.size = Pt(9)
    r.font.color.rgb = RGBColor(89, 89, 89)


def add_cover(doc):
    for _ in range(4):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("国家电网有限公司科技项目")
    set_east_asia_font(r, "黑体")
    r.font.size = Pt(16)
    r.bold = True

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("基于新型电力负荷管理系统的虚拟电厂市场化运营服务支撑技术及应用")
    set_east_asia_font(r, "黑体")
    r.font.size = Pt(18)
    r.bold = True

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(TITLE)
    set_east_asia_font(r, "黑体")
    r.font.size = Pt(22)
    r.bold = True

    for _ in range(2):
        doc.add_paragraph()
    for line in ["课题一：虚拟电厂多元异质资源调节行为分析与智能分类方法", "编制状态：初稿", "编制日期：2026年7月"]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(line)
        set_east_asia_font(r)
        r.font.size = Pt(12)
    doc.add_page_break()


def add_abstract(doc):
    doc.add_heading("摘要", level=1)
    add_para(
        doc,
        "本报告面向“基于新型电力负荷管理系统的虚拟电厂市场化运营服务支撑技术及应用”项目课题一，围绕虚拟电厂多元异质资源在差异化市场环境下的调节行为分析、可调容量与响应能力建模以及智能分类方法开展技术论述。针对当前虚拟电厂聚合资源类型复杂、额定容量难以反映实时可调用能力、用户调节意愿与设备客观能力容易混淆、不同市场场景下资源适配关系不清等问题，报告构建了“影响因素识别—调节意愿建模—动态能力建模—可信可调用能力评估—资源智能分级分类”的总体技术框架。",
    )
    add_para(
        doc,
        "报告首先梳理分布式光伏、独立储能、充电桩及充电站、工业可调负荷、商业楼宇空调等典型资源的调节特性，建立市场信号、环境参数、物理属性、实时状态、用户行为、业务约束和历史反馈等影响因素体系；其次提出调节意愿与动态调节能力双通道影响机理模型，将资源“愿不愿调”和“能不能调”分离建模，并通过场景匹配、历史可靠度和安全校核形成可信可调用能力；再次设计多维行为特征库和数据治理方案，为后续因果解耦、关键时序特征提取、主客体协同建模、自监督表征学习和资源智能分级分类提供数据基础。报告同时给出模型精度不小于90%的目标说明、候选评价指标和验证方案。当前阶段在真实数据尚不完整的情况下，以模型框架、变量体系、数据需求和验证路径为主，后续可结合实际资源台账、市场信号、调节事件和响应曲线开展实证校准。",
    )
    add_para(doc, "关键词：虚拟电厂；多元异质资源；调节意愿；动态调节能力；可信可调用能力；特征库；智能分类")
    doc.add_heading("ABSTRACT", level=1)
    add_para(
        doc,
        "This technical report focuses on Topic 1 of the project, namely behavior analysis and intelligent classification methods for heterogeneous resources in virtual power plants. It proposes an integrated framework covering behavior-factor identification, willingness modeling, dynamic capability modeling, credible callable-capacity evaluation, feature-library construction, and intelligent resource classification. The report distinguishes resource willingness from objective regulation capability, maps market signals, environmental parameters, physical attributes, real-time states, user behavior, business constraints, and historical feedback into observable variables, and defines a verification-oriented technical route for achieving the required model accuracy target of no less than 90%. Where real project data is not yet available, the current draft presents the model framework, data requirements, and validation scheme, leaving clear replacement calibers for future empirical results.",
    )
    add_para(doc, "KEYWORDS: Virtual Power Plant; Heterogeneous Resources; Regulation Willingness; Dynamic Regulation Capability; Callable Capacity; Feature Library; Intelligent Classification")
    doc.add_page_break()


def add_toc_placeholder(doc):
    doc.add_heading("目录", level=1)
    add_para(doc, "（初稿说明：正式提交前可在 Word 中插入或更新自动目录。）")
    toc_items = [
        "摘要",
        "ABSTRACT",
        "1 概述",
        "2 虚拟电厂多元异质资源行为影响因素分析技术研究",
        "3 虚拟电厂资源调节意愿与动态调节能力影响机理模型研究",
        "4 虚拟电厂资源可调容量与响应能力特征建模方法研究",
        "5 面向多元市场调节需求的资源智能分级分类方法研究",
        "6 多维行为特征库构建与数据治理方案",
        "7 模型验证方案与精度评价体系",
        "8 总结与展望",
        "参考文献",
    ]
    add_numbered(doc, toc_items)
    doc.add_page_break()


def chapter_overview(doc):
    doc.add_heading("1 概述", level=1)
    doc.add_heading("1.1 背景意义", level=2)
    add_para(
        doc,
        "随着新型电力系统建设持续推进，分布式光伏、储能、电动汽车、可调负荷、楼宇空调等需求侧和分布式资源规模快速增长。虚拟电厂通过聚合多元资源参与现货、辅助服务、备用、绿电交易等市场，是提升电力系统调节能力和促进资源市场化价值实现的重要形态。与传统集中式电源不同，虚拟电厂聚合资源具有类型多、状态快变、用户行为强相关、运行约束复杂等特点，其可调容量和响应能力不能简单由额定容量相加得到。",
    )
    add_para(
        doc,
        "课题一聚焦多元异质资源调节行为分析与智能分类，目标是建立能够解释资源调节行为形成机理、刻画资源可调容量与响应能力、支撑多元市场适配分类的技术体系。该研究既是虚拟电厂精细化运营的基础，也是后续交易策略推荐、资源调节分析、可调容量评估和能碳协同服务的重要数据与算法底座。",
    )
    add_data_note(
        doc,
        "后续可补充山东虚拟电厂实际接入资源规模、资源类型分布、负荷管理系统数据范围、市场参与场景、历史调节事件数量和典型响应效果，用于增强背景论述的工程真实性。",
    )

    doc.add_heading("1.2 国内外现状", level=2)
    add_para(
        doc,
        "现有虚拟电厂研究通常围绕资源聚合、市场出清、日前/日内交易优化、需求响应激励和辅助服务参与展开。近年来，随着资源类型增多和市场机制细化，研究重点逐步从单一资源或单一市场优化转向多资源、多市场、多时序尺度下的资源行为刻画。一方面，分布式光伏和储能的可调能力受天气、SOC、功率边界、后续运行计划等状态影响；另一方面，充电桩、工业负荷和空调负荷的响应行为还受到用户出行、生产计划、舒适度、风险偏好和历史体验影响。",
    )
    add_para(
        doc,
        "从方法上看，混合效应模型、广义线性模型、离散选择模型、前景理论、时序深度学习、因果图学习、自监督表征学习和聚类分类方法均可为虚拟电厂资源行为建模提供支撑。但在工程落地中，仍存在三类不足：一是资源调节意愿与客观能力混合表述，导致低响应原因难以解释；二是额定容量、实时状态、市场场景和用户授权之间缺少统一映射；三是资源分类往往停留在静态类型划分，难以面向不同市场需求形成可验证的能力等级和适配结果。",
    )

    doc.add_heading("1.3 研究目标与内容", level=2)
    add_para(
        doc,
        "课题一的总体目标是构建虚拟电厂多元异质资源可调容量与响应能力特征模型，并形成面向多元市场调节需求的资源智能分级分类方法。根据项目任务要求，模型精度目标不小于90%。在当前阶段，报告将该指标作为后续验证目标处理，并给出候选评价口径和数据需求，不将尚未完成的真实数据验证表述为已完成结论。",
    )
    add_table(
        doc,
        ["研究内容", "核心任务", "阶段输出"],
        [
            ["多元资源行为影响因素分析", "识别市场信号、环境参数、物理属性、用户行为和业务约束对资源行为的影响", "影响因素体系、资源行为矩阵、研究假设"],
            ["可调容量与响应能力建模", "区分调节意愿和动态调节能力，构建可信可调用能力模型", "意愿模型、能力模型、综合响应能力特征模型"],
            ["资源智能分级分类", "面向不同市场需求建立能力指标、表征学习、聚类分级和市场适配评价", "资源能力等级、市场适配分类结果、约束校核方法"],
            ["多维行为特征库", "设计支撑模型训练、验证和应用的数据主题、字段、质量规则和加工流程", "特征库基础架构、数据字典、验证数据集方案"],
        ],
        widths=[4.0, 7.5, 4.5],
    )

    doc.add_heading("1.4 总体技术路线", level=2)
    add_para(
        doc,
        "课题一技术路线按照“资源识别—特征描述—因素识别—机理分析—模型表达—特征入库—能力评估—智能分类—市场适配”的路径展开。当前阶段重点完成前期调研、资源范围界定、影响因素体系、调节意愿与动态能力影响机理模型、多维行为特征库基础架构和验证方案。后续阶段将在真实数据基础上开展因果解耦、阈值及敏感性分析、关键调节时序特征提取、主观意愿量化、动态能力预测、自监督表征学习和资源智能分级分类。",
    )
    add_table(
        doc,
        ["阶段", "时间范围", "主要研究内容", "主要成果"],
        [
            ["前期调研与方案制定", "2026.03", "收集资料、明确研究对象、确定实施路径", "课题实施方案"],
            ["行为影响因素与机理模型", "2026.04-2026.06", "混合效应模型、广义线性模型、多维行为特征库基础架构", "多维行为机理模型"],
            ["因果模型与敏感性分析", "2026.07-2026.09", "因果模型、因果图学习、参数扰动和敏感性分析", "驱动解耦与敏感性分析结果"],
            ["关键调节时序特征提取", "2026.10-2026.12", "相似度度量、资源调节模式识别、变点与状态转移提取", "调节时序演化特征"],
            ["主观意愿与综合能力建模", "2027.01-2027.06", "行为经济学、前景理论、离散选择模型、主客体约束协同", "主观意愿调节方法与综合能力模型"],
            ["智能分级分类与市场适配", "2027.07-2028.02", "自监督表征学习、无监督聚类、市场适配与约束校核", "资源智能分类结果与总结报告"],
        ],
        widths=[3.0, 3.0, 7.5, 4.0],
    )


def chapter_factors(doc):
    doc.add_heading("2 虚拟电厂多元异质资源行为影响因素分析技术研究", level=1)
    doc.add_heading("2.1 研究内容概述", level=2)
    add_para(
        doc,
        "多元异质资源行为影响因素分析是课题一的基础工作，其任务不是直接给出交易策略，而是回答资源在什么市场、环境和运行条件下愿意参与调节，当前状态下能够提供多大的功率、电量、持续时间和响应速度，以及低响应究竟来自低意愿、低能力还是场景不匹配。为此，本报告将资源行为影响因素划分为市场信号、环境参数、物理属性、实时状态、用户与业务约束、历史反馈六类，并按照资源类型分别分析其作用对象和作用路径。",
    )

    doc.add_heading("2.2 多元异质资源范围与调节特性", level=2)
    add_para(
        doc,
        "第一阶段优先研究分布式光伏、独立储能、充电桩及充电站三类资源，同时将工业可调负荷和商业楼宇空调负荷纳入统一扩展框架。资源选择兼顾阶段任务、数据可获得性、资源代表性和后续市场适配价值。各类资源在能量角色、响应速度、持续能力、外部依赖和用户行为影响方面存在显著差异，因此应采用“统一框架加资源专属子模型”的建模方式。",
    )
    add_table(
        doc,
        ["资源类型", "主要调节方式", "关键状态变量", "主要限制"],
        [
            ["分布式光伏", "限功率、光储协同、预测修正", "光照、云量、当前/预测出力、配储SOC", "天气不确定，单体向上调节空间有限"],
            ["独立储能", "充电、放电、功率跟踪", "SOC、SOH、温度、功率/容量边界", "能量边界、寿命损耗、后续运行计划"],
            ["充电桩及充电站", "移峰充电、降功率、V2G放电", "在线车辆数、当前SOC、目标SOC、离站时间", "车辆接入随机、出行需求、用户授权"],
            ["工业可调负荷", "削减、转移、中断、工序调整", "生产阶段、当前负荷率、库存、工艺约束", "生产安全、产品质量、停产损失"],
            ["商业楼宇空调", "温度设定调整、启停、预冷预热", "室内外温度、热惯性、人员密度、营业状态", "舒适度边界、反弹负荷、营业时段"],
        ],
        widths=[3.2, 3.8, 5.2, 4.0],
    )

    doc.add_heading("2.3 差异化市场环境分析口径", level=2)
    add_para(
        doc,
        "虚拟电厂资源参与的市场场景具有差异化要求。现货市场更关注价格弹性、价差套利、负电价响应和可平移时长；调频市场更关注响应速度、跟踪精度和高频执行能力；备用和爬坡场景更关注可用率、持续时间和提前通知；绿电及能碳相关场景更关注绿色价值、清洁能源消纳和用户价值偏好。相同资源在不同市场中的主导因素并不一致，因而需要将市场需求向量与资源能力向量进行匹配分析。",
    )
    add_table(
        doc,
        ["市场场景", "主要需求特征", "主导影响因素", "适配资源示例"],
        [
            ["现货市场", "分时价格、价差套利、负电价响应、15分钟级调节", "价格弹性、可平移时长、调节成本、预测误差", "储能、充电桩、可转移工业负荷"],
            ["调频市场", "秒级至分钟级响应、跟踪精度、持续调用", "响应速度、爬坡能力、控制精度、通信可靠性", "储能、具备快速控制能力的柔性负荷"],
            ["备用/爬坡", "可用容量、持续时间、提前通知、可靠履约", "可用率、恢复时间、业务约束、安全边界", "储能、工业负荷、空调聚合资源"],
            ["绿电/能碳", "清洁能源消纳、绿色价值、用户偏好", "绿色收益、消纳约束、用户绿色偏好", "光伏、光储联合、具备绿色价值偏好的用户侧资源"],
        ],
        widths=[2.8, 4.5, 5.5, 3.8],
    )

    doc.add_heading("2.4 资源行为影响因素体系", level=2)
    add_para(
        doc,
        "影响因素体系的关键是明确每类因素主要作用于调节意愿、动态调节能力，还是实际执行反馈。市场收益、调节成本、风险感知、任务属性和历史体验主要影响调节意愿；物理属性、实时状态、环境参数、安全约束和恢复状态主要影响动态调节能力；通信状态、控制执行、基线估计和随机扰动则进一步影响实际响应结果。",
    )
    add_table(
        doc,
        ["因素类别", "变量示例", "主要作用对象", "典型作用路径"],
        [
            ["市场信号", "补偿价格、峰谷价差、考核规则、调用频率", "调节意愿、场景匹配", "改变收益、成本与风险感知"],
            ["环境参数", "光照、云量、温度、湿度、季节、时段", "动态调节能力", "修正可用出力、基础负荷和预测可信度"],
            ["物理属性", "额定功率、容量、爬坡速率、响应速度、效率", "动态调节能力", "确定理论功率、能量和响应边界"],
            ["实时状态", "当前功率、SOC、在线车辆数、室温、生产状态", "动态调节能力", "确定当前剩余功率空间和时间窗口"],
            ["用户与业务约束", "出行需求、生产计划、舒适度、授权方式", "调节意愿、动态调节能力", "同时影响用户开放意愿和客观可用边界"],
            ["历史反馈", "历史收益、偏差考核、负面体验、调用疲劳", "调节意愿、可靠度", "形成滞后、学习和疲劳效应"],
        ],
        widths=[2.8, 4.2, 3.5, 5.8],
    )

    doc.add_heading("2.5 影响因素分析方法", level=2)
    add_para(
        doc,
        "影响因素分析采用定性机理识别与后续数据验证相结合的方法。当前阶段主要通过政策机制调研、资源调节特性分析、专家判断和已有阶段材料形成因素矩阵；后续在获得真实数据后，使用混合效应模型、广义线性模型、分段回归、因果图学习和敏感性分析识别因素方向、阈值、交互、滞后和资源异质性。",
    )
    add_numbered(
        doc,
        [
            "建立资源类型、市场场景和调节任务的统一编码。",
            "将价格、补偿、考核、SOC、在线车辆数、温度、持续时间等因素转化为可观测变量。",
            "分别识别变量对调节意愿、动态能力和实际响应结果的作用对象。",
            "在真实样本中开展统计检验、模型拟合、因果解耦和典型事件回放。",
        ],
    )
    add_data_note(
        doc,
        "后续可补充各类资源台账、实时运行曲线、市场价格、调节指令、用户接受记录、响应曲线、偏差考核和收益数据。若有16类资源与4类市场敏感性矩阵的正式标定值，可在本章形成跨资源、跨市场的核心表格。",
    )


def chapter_mechanism(doc):
    doc.add_heading("3 虚拟电厂资源调节意愿与动态调节能力影响机理模型研究", level=1)
    doc.add_heading("3.1 研究任务与问题界定", level=2)
    add_para(
        doc,
        "虚拟电厂资源实际响应行为不能仅由额定容量解释。实际响应不足可能来自三类原因：一是资源具备物理调节能力，但用户不愿意开放；二是用户愿意参与，但资源当前状态不具备足够调节能力；三是资源意愿和能力均存在，但不满足特定市场任务对方向、速度、持续时间、精度和安全边界的要求。因此，本报告将资源行为分解为调节意愿、动态调节能力和场景匹配三类核心状态，并通过历史可靠度和安全校核形成可信可调用能力。",
    )
    add_table(
        doc,
        ["问题", "传统处理方式的不足", "本报告处理方式"],
        [
            ["额定容量不等于实时可调能力", "按装机或额定容量简单折算，忽略当前状态", "引入功率、能量、时间、响应和可用概率等动态能力分量"],
            ["愿不愿调与能不能调混淆", "将低响应直接归因于资源能力不足", "分别建立调节意愿通道和动态能力通道"],
            ["市场需求差异未体现", "同一能力指标用于所有市场", "引入市场任务向量和场景匹配系数"],
            ["历史执行反馈不足", "忽略收益、考核和疲劳对后续行为的影响", "引入历史可靠度和反馈更新机制"],
        ],
        widths=[4.0, 5.8, 6.0],
    )

    doc.add_heading("3.2 调节意愿形成机理", level=2)
    add_para(
        doc,
        "调节意愿是资源所有者或运营主体在特定市场激励、用能需求和风险约束下愿意接受调节的程度。其并非单一变量，而应包括是否参与当前任务、愿意开放多少能力、是否能够在任务持续期间保持响应等多个维度。市场收益提高通常增强调节意愿，但当调节影响生产、出行或舒适度时，补偿需要先覆盖机会成本；当调用频率或持续时间过高时，还可能产生疲劳效应。",
    )
    add_table(
        doc,
        ["意愿维度", "含义", "可观测代理变量"],
        [
            ["参与概率 W_part", "是否接受当前调节任务", "接受邀约、参与记录、是否签约或授权"],
            ["开放比例 W_open", "愿意开放的能力占客观能力的比例", "申报容量/客观能力估计、授权比例"],
            ["保持概率 W_keep", "任务持续期间继续响应的概率", "中途退出、响应中断、持续达标情况"],
        ],
        widths=[3.5, 5.0, 7.0],
    )
    add_para(
        doc,
        "概念表达为：W_i(t,m)=f(预计收益-调节成本, 风险感知, 调节任务属性, 用户偏好, 当前业务需求, 历史参与反馈)。其中，t表示时刻，m表示市场或调节场景，i表示资源对象。具体函数形式可根据数据条件选择Logit/Probit、离散选择模型、前景理论修正模型或广义线性混合模型。",
    )

    doc.add_heading("3.3 动态调节能力形成机理", level=2)
    add_para(
        doc,
        "动态调节能力是资源在特定时刻和运行状态下实际能够提供的上下调功率、电量、持续时间、响应速度、恢复时间、调节精度和可用概率。与调节意愿不同，动态能力首先受物理属性和实时状态约束，再受环境参数、业务状态、安全边界和历史调用状态修正。不同资源的能力函数具有显著差异，应采用资源专属子模型。",
    )
    add_table(
        doc,
        ["能力分量", "含义", "主要影响因素"],
        [
            ["P_up/P_down", "向上/向下调节功率", "当前功率、额定功率、SOC、在线数量、负荷率"],
            ["E_up/E_down", "向上/向下可调电量", "容量、SOC、剩余停车时间、可转移负荷、库存"],
            ["T_resp", "响应时间", "控制方式、通信链路、设备类型、人工确认流程"],
            ["T_sustain", "最大持续时间", "能量边界、舒适度边界、生产计划、天气窗口"],
            ["T_recover", "恢复时间", "反弹负荷、SOC恢复、工艺恢复、用户需求补偿"],
            ["Acc", "调节精度", "控制粒度、基线估计、跟踪误差、市场考核规则"],
            ["Avail", "可用概率", "设备健康、通信状态、历史成功率、业务可用窗口"],
        ],
        widths=[3.2, 5.0, 7.2],
    )
    add_para(
        doc,
        "概念表达为：C_i(t)=g_i(资源物理属性, 实时运行状态, 外部环境, 基线用能需求, 业务和安全约束, 历史调用状态)。其中，g_i随资源类型变化：光伏由光照、预测出力、当前出力和配储状态决定；储能由SOC、功率、容量、温度和计划SOC轨迹决定；充电桩由在线车辆数、当前/目标SOC和剩余停车时间决定；工业负荷由生产阶段、工艺约束和库存决定；空调负荷由室内外温度、建筑热惯性和舒适度边界决定。",
    )

    doc.add_heading("3.4 意愿与能力交互机理", level=2)
    add_para(
        doc,
        "调节意愿和动态能力不是简单并列关系，而是共同约束实际响应。能力是基础，没有客观剩余能力时，提高补偿也不能形成实际响应；意愿是开放条件，设备具备能力但用户未授权时，能力不能被调用；业务状态可能同时影响两者，例如生产任务既会降低参与意愿，也会压缩客观可调空间；市场任务则形成方向、速度、持续时间和精度的匹配要求。",
    )
    add_para(
        doc,
        "资源在时刻t面向市场场景m的可信可调用能力可表示为：A_i(t,m)=C_i(t) x W_open,i(t,m) x Q_match,i(t,m) x R_history,i(t) x S_safe,i(t)。其中C_i(t)为当前客观动态调节能力，W_open为意愿开放比例，Q_match为场景匹配程度，R_history为历史可靠度，S_safe为安全校核结果。上述公式是阶段性机理表达，具体函数形式和参数需通过真实数据验证。",
    )

    doc.add_heading("3.5 实际响应与反馈机制", level=2)
    add_para(
        doc,
        "实际响应行为由可信可调用能力、控制指令、通信和执行状态以及随机扰动共同决定。响应结果进一步形成四类反馈：实际净收益更新用户收益体验和下一次参与意愿；响应偏差及考核更新风险感知和历史可靠度；设备损耗及状态变化影响后续动态能力；生产、出行或舒适度影响更新后续授权范围和持续参与意愿。",
    )
    add_data_note(
        doc,
        "后续可补充真实调节事件的event_id、指令下发时间、目标功率、基线功率、实际功率、响应延迟、持续时间、跟踪误差、完成比例、反弹功率、净收益、考核费用和失败原因。利用这些字段可以验证低响应原因分解和反馈机制。",
    )


def chapter_capacity(doc):
    doc.add_heading("4 虚拟电厂资源可调容量与响应能力特征建模方法研究", level=1)
    doc.add_heading("4.1 研究内容概述", level=2)
    add_para(
        doc,
        "可调容量与响应能力特征模型是课题一的核心考核对象。项目要求构建虚拟电厂多元异质资源可调容量与响应能力特征模型，模型精度不小于90%。本报告将该模型理解为对资源在特定时刻、市场场景和安全约束下可提供调节能力的综合刻画，既包括客观动态能力，也包括主观开放意愿、场景匹配和历史可靠度。",
    )

    doc.add_heading("4.2 主观调节意愿建模", level=2)
    add_para(
        doc,
        "主观调节意愿模型面向用户或资源运营主体的参与决策。根据数据可得性，可采用三类方法：一是使用接受邀约、申报容量和中途退出等行为变量构造意愿代理指标；二是使用前景理论和离散选择模型刻画用户在收益、损失和不确定性下的偏好；三是使用广义线性混合模型刻画价格、调用频率、持续时间、风险和用户异质性对参与概率的影响。",
    )
    add_table(
        doc,
        ["建模对象", "候选方法", "输入变量", "输出变量"],
        [
            ["是否参与", "Logit/Probit、广义线性混合模型", "补偿价格、持续时间、调用频率、用户类型、历史收益", "参与概率"],
            ["能力开放比例", "分数响应模型、Beta回归", "申报容量、客观能力估计、风险偏好、任务属性", "开放比例"],
            ["阈值与疲劳效应", "分段回归、面板模型", "补偿水平、近期调用次数、累计调用时长", "补偿阈值、疲劳指数"],
            ["风险偏好修正", "前景理论、离散选择模型", "收益波动、偏差考核、损失厌恶参数", "修正参与效用"],
        ],
        widths=[3.2, 4.2, 5.8, 3.0],
    )

    doc.add_heading("4.3 客观动态能力建模", level=2)
    add_para(
        doc,
        "客观动态能力模型面向资源设备和运行状态。第一版可优先采用可解释物理约束模型，根据额定功率、容量、SOC、当前功率、在线车辆数、室内温度、生产状态等变量计算理论能力边界；在历史响应数据积累后，可进一步引入时序模型、LSTM、Transformer或广义加性模型，对能力预测进行数据修正和不确定性估计。",
    )
    add_table(
        doc,
        ["资源类型", "能力建模重点", "关键输入", "主要输出"],
        [
            ["分布式光伏", "预测出力与限功率空间", "辐照度、云量、当前/预测出力、配储SOC", "向下调节功率、预测误差、可用概率"],
            ["独立储能", "功率边界与能量边界", "SOC、SOH、温度、额定功率、计划SOC", "上下调功率、电量、持续时间"],
            ["充电桩/站", "车辆接入概率与充电需求窗口", "在线车辆数、当前SOC、目标SOC、预计离站时间", "可削减功率、V2G放电能力、持续时间"],
            ["工业负荷", "工艺约束与生产调整空间", "生产阶段、负荷率、库存、订单紧迫度", "可中断/可转移功率、提前通知需求"],
            ["空调负荷", "热惯性与舒适度边界", "室内外温度、设定值、人员密度、营业状态", "短时削减功率、最大持续时间、反弹负荷"],
        ],
        widths=[3.0, 4.0, 5.5, 4.0],
    )

    doc.add_heading("4.4 主客体约束一体化建模", level=2)
    add_para(
        doc,
        "在虚拟电厂聚合层面，单个资源的意愿和能力还需要考虑源-荷-储协同、资源互补性、控制一致性和市场任务组合。主客体约束一体化建模应将用户主观偏好、资源客观能力、聚合控制约束和市场场景需求共同纳入综合响应能力模型。后续可引入多智能体协同交互方法，刻画不同资源之间的协同性、互补性和冲突约束。",
    )
    add_numbered(
        doc,
        [
            "主体侧建模：用户价格敏感度、用能偏好、绿色价值取向、风险偏好和授权方式。",
            "客体侧建模：资源物理属性、实时状态、响应速度、持续时间、恢复间隔和安全边界。",
            "聚合侧建模：资源组合约束、控制策略、通信链路、聚合商调度目标和市场任务要求。",
            "输出侧建模：协同可调容量、综合响应能力、可靠度、市场适配度和限制因素解释。",
        ],
    )

    doc.add_heading("4.5 模型输出与解释", level=2)
    add_para(
        doc,
        "综合响应能力特征模型应输出可用于运营决策和后续分类的结构化结果，包括当前可信向上/向下调节功率、可调电量、最大持续时间、响应速度、跟踪精度、恢复时间、可用概率、意愿评分、可靠度评分、场景适配度和主要限制因素。相比单一容量数值，该模型更适合解释资源在不同市场中的可用边界和适配关系。",
    )
    add_data_note(
        doc,
        "后续可补充真实模型输入输出样例、分资源建模公式、训练验证样本划分、误差统计、限制因素解释案例和与额定容量法、单一能力法的对比结果。",
    )


def chapter_classification(doc):
    doc.add_heading("5 面向多元市场调节需求的资源智能分级分类方法研究", level=1)
    doc.add_heading("5.1 研究内容概述", level=2)
    add_para(
        doc,
        "资源智能分级分类的目标不是仅按资源类型贴标签，而是根据资源可调容量、响应速度、持续时间、精度、可靠度、调节成本、用户开放意愿和市场需求适配度，形成面向现货、调频、备用、绿电等不同市场场景的能力等级和分类结果。该部分属于课题一后续完整研究内容，当前报告先给出方法框架和验证口径。",
    )

    doc.add_heading("5.2 多维能力指标体系", level=2)
    add_para(
        doc,
        "多维能力指标体系应覆盖功率、电量、时间、响应、可靠、经济和市场适配等维度。对于不同市场，各指标权重不同。例如调频场景重视响应速度和跟踪精度，现货场景重视价格弹性和可平移时长，备用场景重视持续时间和可靠度，绿电场景重视绿色价值和消纳协同。",
    )
    add_table(
        doc,
        ["指标维度", "指标示例", "主要用途"],
        [
            ["功率能力", "上下调功率、额定功率占比、聚合可调功率", "判断调节幅度"],
            ["能量能力", "可调电量、SOC空间、可转移负荷量", "判断持续调节能力"],
            ["时间能力", "响应时间、持续时间、恢复时间、提前通知时间", "匹配市场时间尺度"],
            ["调节质量", "跟踪精度、完成比例、偏差率、反弹负荷", "评估执行效果"],
            ["可靠性", "可用率、成功率、历史偏差、通信可用性", "评估履约风险"],
            ["经济性", "调节成本、净收益、补偿阈值、价格弹性", "评估参与价值"],
            ["市场适配", "场景匹配度、约束校核结果、市场适配命中率", "形成资源分类结果"],
        ],
        widths=[3.0, 5.3, 7.0],
    )

    doc.add_heading("5.3 智能分级分类方法", level=2)
    add_para(
        doc,
        "第一版可采用多准则决策或TOPSIS方法形成可解释的基础等级，作为人工/规则基准；在样本积累后，引入自监督表征学习和对比学习，从历史运行曲线、调节事件序列、市场信号和响应结果中学习资源行为表示；再通过无监督聚类、半监督分类或规则校核形成智能能力等级和市场适配分类结果。",
    )
    add_numbered(
        doc,
        [
            "构建资源能力指标宽表，形成分资源、分事件、分市场场景的样本。",
            "通过规则基准或专家标定形成基础等级，用于解释和初始校验。",
            "使用自监督表征学习提取资源时序行为特征，减少对人工标签依赖。",
            "通过聚类区分度、等级稳定性和人工/规则基准一致性验证分类可靠性。",
            "在典型市场场景中回放分类结果，评估资源配置效率和响应执行效果提升。",
        ],
    )

    doc.add_heading("5.4 市场适配与约束校核", level=2)
    add_para(
        doc,
        "资源分类结果需要进一步通过市场适配与约束校核，避免将能力等级高但不满足特定场景要求的资源错误纳入调用。例如储能在调频场景中具有较高适配度，但若SOC接近边界则当期可用能力需折减；充电桩聚合资源在现货移峰中具有价值，但用户离站时间过近时不宜参与长时调用；空调负荷可短时削减，但需要考虑舒适度和反弹负荷。",
    )
    add_data_note(
        doc,
        "后续可补充资源能力等级样本、市场需求向量、人工/规则分类基准、聚类轮廓系数、等级稳定性、市场适配命中率和典型场景回放结果。",
    )


def chapter_library(doc):
    doc.add_heading("6 多维行为特征库构建与数据治理方案", level=1)
    doc.add_heading("6.1 研究内容概述", level=2)
    add_para(
        doc,
        "多维行为特征库是影响机理研究、能力建模和智能分类的共同数据基础。该特征库不应被理解为独立软件建设任务，而应服务于资源画像、影响因素分析、调节意愿识别、动态能力估计、实际响应评价和后续分级分类。其核心是以资源编号、时间区间和调节事件编号为主线，将资源档案、运行状态、市场信号、外部环境、用户行为和执行结果进行统一关联。",
    )

    doc.add_heading("6.2 数据架构设计", level=2)
    add_para(
        doc,
        "建议采用原始层、标准层、特征层、模型层和应用层五层架构。原始层保留来自负荷管理系统、市场系统、气象系统、资源侧平台和调节执行记录的原始数据；标准层完成统一资源编号、时间区间、单位、状态编码和事件编号；特征层生成静态特征、状态特征、时序特征和统计特征；模型层存储意愿、能力、适配度和可信可调用能力；应用层支撑资源画像、能力评估、调节分析和智能分类。",
    )
    add_table(
        doc,
        ["数据层", "主要内容", "作用"],
        [
            ["原始层", "市场信号、环境数据、资源运行、资源台账、用户行为、调节事件和结果", "保留原始证据和追溯依据"],
            ["标准层", "统一时间、单位、资源编号、市场场景、事件编号和状态编码", "解决跨系统关联问题"],
            ["特征层", "基线、偏差、可用率、价格弹性、疲劳指数、可靠度等", "支撑模型训练和分析"],
            ["模型层", "意愿评分、动态能力、场景匹配、可信可调用能力", "形成可调用能力评估结果"],
            ["应用层", "资源画像、能力评估、调节事件回放、市场适配分类", "支撑运营服务和后续课题承接"],
        ],
        widths=[2.6, 8.5, 5.0],
    )

    doc.add_heading("6.3 核心主题表设计", level=2)
    add_table(
        doc,
        ["主题表", "核心字段示例", "主要用途"],
        [
            ["resource_master", "资源编号、类型、额定功率、容量、接入节点、控制方式", "资源识别和静态画像"],
            ["resource_state_ts", "时间、实时功率、SOC、SOH、在线数量、可用状态", "动态能力估计"],
            ["external_environment_ts", "气象、温度、光照、湿度、节假日、系统负荷", "环境修正和场景识别"],
            ["market_signal", "市场类型、价格、补偿、考核、指令要求、时间分辨率", "意愿和市场适配建模"],
            ["user_behavior", "授权方式、接受记录、退出记录、用户偏好、历史参与率", "调节意愿建模"],
            ["regulation_event", "事件编号、指令编号、开始/结束时间、方向、目标功率、基线", "调节事件组织"],
            ["regulation_result", "实际功率、响应延迟、持续时间、偏差、收益、失败原因", "模型验证和反馈更新"],
            ["behavior_feature", "参与率、开放比例、可靠度、意愿评分、可信能力、适配度", "模型输出和分类输入"],
        ],
        widths=[3.5, 8.5, 4.0],
    )

    doc.add_heading("6.4 数据对齐与质量控制", level=2)
    add_para(
        doc,
        "虚拟电厂多源数据的关键难点在于时间尺度不同、字段口径不同和事件关联困难。建议市场信号采用ts_start、ts_end、resolution_s三元组表达时间区间，资源运行数据保留秒级或分钟级原始采样，调节事件通过event_id贯穿指令、基线、实际响应和结果反馈。对于调频AGC、绿电凭证等异构字段，可在原始层使用可扩展字段保存，同时在标准层抽取统一分析字段。",
    )
    add_bullets(
        doc,
        [
            "完整性：核心资源档案字段不得为空，调节事件必须具备指令、基线、实际功率和结果记录。",
            "准确性：功率、能量、价格、SOC、温度等字段统一单位并检查物理范围。",
            "时序一致性：市场、气象、状态、指令和结果数据统一时区，记录采样误差。",
            "逻辑一致性：不支持V2G的充电桩不得出现放电状态，光伏夜间无配储时不得记录正向发电能力。",
            "异常处理：原始数据不直接覆盖，保留异常标识；调节事件关键区间原则上不进行无依据填补。",
        ],
    )
    add_data_note(
        doc,
        "后续可补充真实数据库表结构、字段样例、数据来源系统、采样频率、字段覆盖率、缺失率、清洗率、数据质量报告和特征计算任务清单。",
    )


def chapter_validation(doc):
    doc.add_heading("7 模型验证方案与精度评价体系", level=1)
    doc.add_heading("7.1 精度目标说明", level=2)
    add_para(
        doc,
        "根据项目任务要求，课题一需构建虚拟电厂多元异质资源可调容量与响应能力特征模型，模型精度不小于90%。当前阶段尚需进一步明确该指标的评价对象、样本划分和计算口径。因此，本报告将90%作为必须达到的模型验证目标，并提出多类候选评价口径，待真实数据和项目组考核口径明确后选定最终指标。",
    )
    add_table(
        doc,
        ["评价对象", "候选指标", "90%目标可能含义", "适用场景"],
        [
            ["可调容量预测", "MAPE、RMSE、MAE、区间命中率", "预测误差满足阈值或命中率不低于90%", "功率/电量连续值预测"],
            ["响应能力分类", "Accuracy、F1、规则基准一致率", "分类准确率或一致率不低于90%", "资源等级和能力标签"],
            ["调节事件完成", "完成比例、达标率、响应成功率", "调节事件达标率不低于90%", "历史事件回放和执行评价"],
            ["市场适配分类", "适配命中率、约束校核通过率", "市场适配判断命中率不低于90%", "多市场资源推荐"],
            ["意愿预测", "AUC、Precision、Recall、参与率预测误差", "参与意愿识别具备较高区分度", "用户行为和授权建模"],
        ],
        widths=[3.2, 4.4, 5.0, 3.2],
    )

    doc.add_heading("7.2 验证数据集设计", level=2)
    add_para(
        doc,
        "验证数据集应以调节事件为核心样本单元，每条样本关联事件前资源状态、市场信号、环境参数、用户行为、任务要求和执行结果。对于连续时序模型，应保留事件前、事件中和事件后的完整曲线，以提取持续、波动、恢复和反弹特征。样本划分应按照资源类型、市场场景和时间区间进行分层，避免同一资源同一时段的数据泄漏导致精度虚高。",
    )
    add_numbered(
        doc,
        [
            "训练集：用于模型参数估计和特征选择。",
            "验证集：用于阈值、超参数和特征组合调优。",
            "测试集：用于最终精度评价，不参与模型训练。",
            "跨场景验证集：用于检验跨资源类型、跨市场场景和跨时间尺度的泛化能力。",
        ],
    )

    doc.add_heading("7.3 评价与闭环优化", level=2)
    add_para(
        doc,
        "模型验证不应仅看单一平均精度，还应输出分资源、分场景、分时间尺度、分能力分量的误差统计和限制因素解释。对未达标样本，应分析是数据缺失、基线误差、低意愿、低能力、场景不匹配、通信失败还是控制执行问题，并将分析结果反馈到特征库和模型参数更新中。",
    )
    add_table(
        doc,
        ["验证内容", "方法", "输出"],
        [
            ["调节意愿模型", "Logit/Probit、混合效应模型、AUC和混淆矩阵", "参与概率、开放比例、阈值和疲劳效应"],
            ["动态能力模型", "物理约束校核、时序预测误差、事件回放", "上下调功率、电量、持续时间、响应速度"],
            ["可信能力模型", "目标-实际对比、分资源误差统计", "可信可调用能力误差和主要限制因素"],
            ["智能分类模型", "聚类区分度、等级稳定性、规则基准一致率", "资源能力等级和市场适配分类"],
            ["闭环优化", "滚动训练、误差归因、数据质量反馈", "模型版本更新和质量改进清单"],
        ],
        widths=[3.4, 6.0, 6.5],
    )
    add_data_note(
        doc,
        "后续可补充真实历史调节结果、样本量、训练/验证/测试划分、模型精度表、分资源误差表、典型失败案例、消融实验和与基准模型的对比结果。",
    )


def chapter_conclusion(doc):
    doc.add_heading("8 总结与展望", level=1)
    doc.add_heading("8.1 总结", level=2)
    add_para(
        doc,
        "本报告围绕课题一“虚拟电厂多元异质资源调节行为分析与智能分类方法”，形成了覆盖完整研究周期的技术报告初稿。报告从虚拟电厂多元异质资源调节行为难以统一刻画的工程问题出发，提出了影响因素体系、调节意愿与动态调节能力双通道影响机理模型、可信可调用能力表达、多维行为特征库、可调容量与响应能力特征建模方法、智能分级分类方法以及模型验证与精度评价体系。",
    )
    add_para(
        doc,
        "当前阶段已经具备较成熟支撑的内容包括：前期调研和实施方案、资源范围与调节特性分析、差异化市场环境下的行为影响因素体系、调节意愿与动态调节能力影响机理模型、多维行为特征库基础架构和数据需求清单。后续需要在真实数据基础上进一步完成因果解耦、敏感性分析、关键调节时序特征提取、主观意愿量化、动态能力预测、自监督表征学习和市场适配分类验证。",
    )

    doc.add_heading("8.2 与课题四的承接关系", level=2)
    add_para(
        doc,
        "课题一不是课题四的普通前置材料，而是课题四实现智能化、精细化、可落地运营服务的数据与算法底座。课题一输出的多维行为特征库、可调容量与响应能力模型、能力分级分类结果以及市场适配与约束校核结果，可支撑课题四开展资源调节分析、可调容量评估、交易策略推荐、交易评估与能碳服务。",
    )

    relation_img = None
    for p in ROOT.glob("*.png"):
        if "课题一与课题四" in p.name:
            relation_img = p
            break
    if relation_img and relation_img.exists():
        try:
            doc.add_picture(str(relation_img), width=Inches(5.8))
            add_caption(doc, "图8-1 课题一输出与课题四承接关系示意")
        except Exception:
            add_para(doc, "（图8-1 课题一输出与课题四承接关系示意：当前生成环境未能插入图片，后续可补充项目根目录同名PNG。）")

    doc.add_heading("8.3 展望", level=2)
    add_bullets(
        doc,
        [
            "完善真实数据接入：优先获取日前/实时价格、系统负荷、资源运行状态、调节事件、响应曲线、用户授权和结算数据。",
            "完成模型实证验证：明确90%精度评价口径，形成分资源、分场景、分时间尺度的验证结果。",
            "加强因果与时序研究：识别价格、天气、SOC、授权和业务状态对资源行为的直接效应、交互效应和滞后效应。",
            "推进智能分类应用：将资源能力等级、市场适配分类和约束校核结果接入虚拟电厂运营服务模块。",
            "形成可复用成果：沉淀数据字典、特征工程规范、模型验证规范和面向多市场运营的资源评价方法。",
        ],
    )

    doc.add_heading("参考文献", level=1)
    add_para(doc, "（初稿占位：正式提交前应结合项目可研报告、政策文件、市场规则、标准规范和公开文献补充完整参考文献，并核验外部政策与案例来源。）")


def main():
    doc = Document()
    configure_styles(doc)
    add_cover(doc)
    add_abstract(doc)
    add_toc_placeholder(doc)
    chapter_overview(doc)
    chapter_factors(doc)
    chapter_mechanism(doc)
    chapter_capacity(doc)
    chapter_classification(doc)
    chapter_library(doc)
    chapter_validation(doc)
    chapter_conclusion(doc)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
