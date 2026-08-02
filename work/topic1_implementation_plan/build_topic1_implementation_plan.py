from copy import deepcopy
from pathlib import Path
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


ROOT = Path(r"D:\myDocu\project_postg\VPP_program")
TEMPLATE = Path(r"D:\wechat\cunchu\xwechat_files\wxid_bwerc1yl4z4k22_d623\temp\RWTemp\2026-07\8115529b7fa47ec7594d7a371c4817cc\课题3实施方案.docx")
OUT = ROOT / "outputs" / "reports" / "课题一实施方案.docx"


def clear_paragraph(paragraph):
    p = paragraph._p
    for child in list(p):
        if child.tag != qn("w:pPr"):
            p.remove(child)


def set_text(paragraph, text, bold=False, align=None):
    clear_paragraph(paragraph)
    run = paragraph.add_run(text)
    run.bold = bold
    if align is not None:
        paragraph.alignment = align


def set_cell_text(cell, text):
    p = cell.paragraphs[0]
    clear_paragraph(p)
    p.add_run(text)
    for p in cell.paragraphs[1:]:
        clear_paragraph(p)


def remove_body_after(doc, last_paragraph):
    body = doc._body._element
    reached = False
    for child in list(body):
        if child is last_paragraph._p:
            reached = True
            continue
        if reached and child.tag != qn("w:sectPr"):
            body.remove(child)


def add_paragraph(doc, text="", style="Normal", bold=False):
    p = doc.add_paragraph(style=style)
    if text:
        p.add_run(text).bold = bold
    return p


def add_subtitle(doc, text):
    p = add_paragraph(doc, text, style="Heading 3")
    return p


def clone_table(doc, template_table):
    clone = deepcopy(template_table._tbl)
    body = doc._body._element
    body.insert(len(body) - 1, clone)
    return doc.tables[-1]


def add_update_fields(doc):
    settings = doc.settings.element
    update = settings.find(qn("w:updateFields"))
    if update is None:
        update = OxmlElement("w:updateFields")
        settings.append(update)
    update.set(qn("w:val"), "true")


def fill_organization_table(table):
    rows = [
        ["序号", "课题设置", "项目牵头单位", "课题牵头单位", "课题负责人", "合作单位", "合作单位分工"],
        [
            "课题1",
            "虚拟电厂多元异质资源调节行为分析与智能分类方法",
            "国网山东省电力公司",
            "国网能源研究院有限公司",
            "吴潇雨\n李龙",
            "国网能源研究院有限公司",
            "（1）融合行为经济学、绿色价值与多智能体协同的虚拟电厂资源可调容量与响应能力分析方法研究\n（2）面向多元市场调节需求的虚拟电厂资源多能力维度自监督智能分级分类方法研究",
        ],
        [
            "课题1",
            "虚拟电厂多元异质资源调节行为分析与智能分类方法",
            "国网山东省电力公司",
            "国网能源研究院有限公司",
            "吴潇雨\n李龙",
            "清华大学",
            "（1）差异化市场环境下虚拟电厂多元资源行为影响因素分析与关键调节时序特征研究\n（2）融合行为经济学、绿色价值与多智能体协同的虚拟电厂资源可调容量与响应能力分析方法研究\n（3）面向多元市场调节需求的虚拟电厂资源多能力维度自监督智能分级分类方法研究",
        ],
    ]
    for row, values in zip(table.rows, rows):
        for cell, value in zip(row.cells, values):
            set_cell_text(cell, value)


def fill_schedule_table(table):
    rows = [
        ["序号", "时间段", "内         容"],
        ["1", "2026.03", "研究内容：\n1. 开展课题前期调研，收集、整理相关资料及数据；\n2. 明确研究目标和技术路线，编制课题实施方案。\n阶段成果：\n1. 形成课题实施方案。"],
        ["2", "2026.04 - 2026.06", "研究内容：\n1. 研究混合效应模型与广义线性模型，量化差异化市场环境对资源行为的影响；\n2. 建立涵盖市场信号、环境参数与物理属性的资源多维行为特征库基础架构。\n阶段成果：\n1. 提出虚拟电厂资源调节意愿与动态调节能力影响机理模型。"],
        ["3", "2026.07 - 2026.09", "研究内容：\n1. 研发基于结构因果模型与因果图学习的驱动因素解耦方法；\n2. 识别非线性特征、关键响应阈值区间与决策敏感性。\n阶段成果：\n1. 提出资源调节行为关键驱动因素解耦与异质资源调节决策敏感性特征模型。"],
        ["4", "2026.10 - 2026.12", "研究内容：\n1. 提取各类资源的基准运行曲线与典型调节模式；\n2. 开展资源调节全周期特征解构，识别持续、波动与恢复等阶段性时序特征。\n阶段成果：\n1. 提出资源调节全周期调节特征演化规律特征提取方案。"],
        ["5", "2027.01 - 2027.03", "研究内容：\n1. 研究融合价格敏感性、用能偏好与绿色价值取向的多源行为因子；\n2. 引入前景理论与离散选择模型，刻画风险和不确定性下的参与偏好。\n阶段成果：\n1. 提出融合行为经济学的主观意愿调节方法。"],
        ["6", "2027.04 - 2027.06", "研究内容：\n1. 研究资源客观物理调节能力特征映射模型；\n2. 开展多智能体协同下的源-荷-储交互分析和组合调节潜力评估。\n阶段成果：\n1. 提出资源调节特征高维映射与时序响应能力建模方法；\n2. 提出虚拟电厂整体可调容量与综合响应特性的协同能力表征方案；\n3. 申请相关发明专利1项。"],
        ["7", "2027.07 - 2027.09", "研究内容：\n1. 解析多元市场需求，构建响应速度、持续性等多维能力指标体系；\n2. 运用自监督学习与无监督聚类，挖掘海量资源特征的潜在分布。\n阶段成果：\n1. 提出虚拟电厂资源多维度静态基础分级分类方法；\n2. 提出基于自监督学习与无监督聚类的智能分级分类方法。"],
        ["8", "2027.10 - 2027.12", "研究内容：\n1. 构建市场适配度评估模型，研究资源能力与市场需求的匹配指数；\n2. 引入物理、运行和协同约束开展匹配校核。\n阶段成果：\n1. 提出资源市场适配度评估与能力匹配校核方法。"],
        ["9", "2028.01 - 2028.02", "研究内容：\n1. 整理核心技术成果，撰写学术论文与技术报告；\n2. 完成知识产权申报与结题验收准备。\n阶段成果：\n1. 发表或录用核心期刊或三大检索论文1篇；\n2. 提交《虚拟电厂多元异质资源调节行为分析与智能分类方法》技术报告。"],
    ]
    for row, values in zip(table.rows, rows):
        for cell, value in zip(row.cells, values):
            set_cell_text(cell, value)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = Document(TEMPLATE)
    original_tables = list(doc.tables)

    # Cover page and units: retain the source template typography and positions.
    p = doc.paragraphs
    set_text(p[6], "虚拟电厂多元异质资源调节行为分析")
    set_text(p[7], "与智能分类方法")
    set_text(p[8], "实施方案")
    set_text(p[9], "Research and Implementation Plan for Regulation Behavior Analysis and Intelligent Classification of Diverse Heterogeneous Virtual Power Plant Resources")
    set_text(p[14], "国网能源研究院有限公司")
    set_text(p[15], "国网山东省电力公司")
    set_text(p[16], "清华大学")
    set_text(p[17], "2026年7月")

    # Keep the cover and the template TOC, including the section break after it.
    remove_body_after(doc, p[34])

    add_paragraph(doc, "一、目的和意义", "Heading 1")
    add_paragraph(doc, "1.1 研究背景", "Heading 2")
    add_paragraph(doc, "虚拟电厂是聚合分布式电源、储能、可调负荷和电动汽车等资源参与电力系统运行与市场交易的重要组织形态。随着新能源占比持续提升和电力市场机制不断完善，资源调节已由单一削峰场景逐步拓展至电能量、调频、爬坡、需求响应等多元场景。不同场景对响应速度、持续时间、调节方向、可靠性和经济性提出了差异化要求，虚拟电厂需要具备对异质资源可调用能力进行精细识别和动态配置的基础能力。")
    add_paragraph(doc, "课题一面向虚拟电厂资源侧这一基础环节，重点解决“资源是否愿意参与、当前能够调多少、能够持续多久、适合参与何种市场”的连续认知问题。资源的设备参数、实时状态、外部环境、市场激励、用户偏好和历史履约表现共同影响实际响应结果，单纯依据额定容量或静态标签难以反映真实可调用能力，也难以为后续资源聚合、市场申报和运营优化提供可靠输入。")
    add_paragraph(doc, "因此，有必要建立覆盖行为影响因素、关键调节时序特征、可调容量、响应能力及市场适配性的统一研究框架，将多源异构信息转化为可计算、可解释、可验证的资源能力画像，为项目其他课题的套餐设计、市场运营优化、阻塞管理和示范应用提供基础数据与模型支撑。")
    add_paragraph(doc, "1.2 研究必要性、目的和意义", "Heading 2")
    add_subtitle(doc, "1.2.1 研究必要性")
    add_paragraph(doc, "虚拟电厂资源具有类型多、规模分散、控制方式不同和行为不确定性强等特点。光伏出力受辐照和天气影响显著，储能能力受荷电状态与寿命约束影响，可调负荷和充电资源则同时受到生产计划、出行需求、舒适度和用户授权等约束。市场价格、补偿机制、调用频率、考核规则和通知时间的变化，又会进一步改变资源的参与意愿与实际执行质量。若缺乏对这些因素的系统分析，容易出现申报能力偏高、调用偏差增大或资源与市场需求错配等问题。")
    add_subtitle(doc, "1.2.2 研究目的")
    add_paragraph(doc, "本课题拟构建虚拟电厂多元异质资源调节行为分析与智能分类方法体系：首先，识别并解耦差异化市场环境、资源物理属性和用户行为等因素对调节行为的影响，提取关键调节时序特征；其次，融合行为经济学、绿色价值与多智能体协同分析，形成资源可调容量与响应能力的综合表征；最后，面向多元市场调节需求建立多能力维度自监督智能分级分类方法，实现资源能力与典型市场场景的精准匹配。")
    add_subtitle(doc, "1.2.3 研究意义")
    add_paragraph(doc, "研究成果将形成贯通“数据—特征—能力—分类—应用”的资源认知链条。一方面，可为虚拟电厂的资源准入、聚合编组、能力申报与履约评估提供可解释的量化依据；另一方面，可向后续课题输出资源行为特征、能力边界和市场适配结果，支撑多元市场套餐优化、阻塞管理及智能运营服务模块的协同开发。")

    add_paragraph(doc, "二、研究内容和实施方案", "Heading 1")
    add_paragraph(doc, "2.1 研究内容", "Heading 2")
    add_paragraph(doc, "本课题围绕“特征解耦、能力量化、智能分级”三条主线展开，形成由资源行为认知到市场应用的递进式研究体系。研究对象包括分布式电源、储能、可调负荷、充电设施等典型资源，研究内容重点关注资源在多元市场与复杂运行场景下的实际可调用能力，而非仅以设备额定参数作为评价依据。")
    add_subtitle(doc, "（1）差异化市场环境下虚拟电厂多元资源行为影响因素分析与关键调节时序特征研究")
    add_paragraph(doc, "研究多元市场激励信号与用户主观行为特征之间的作用机理，分析价格、补偿、考核、调用频率、持续时间和通知时间等因素对资源调节意愿与动态调节能力的影响路径；构建基于混合效应模型、广义线性模型、结构因果模型和因果图学习的关键驱动因素解耦方法，分离量化多维因素对异质资源调节决策的影响；研究资源调节全周期的持续、波动、恢复等阶段性行为模式，提取基准曲线、最大持续时间、最大爬坡率和恢复间隔等关键时序特征，构建多维行为特征库。")
    add_subtitle(doc, "（2）融合行为经济学、绿色价值与多智能体协同的虚拟电厂资源可调容量与响应能力分析方法研究")
    add_paragraph(doc, "研究融合价格敏感度、用能偏好、风险偏好和绿色价值取向的多源行为因子建模方法，利用前景理论与离散选择机制刻画用户主观参与偏好；研究基于深度表示学习的资源调节特征高维映射与时序响应能力建模方法，对上下调功率、可调电量、响应时延、持续时间、恢复时间和跟踪精度等客观能力进行结构化表征；研究多智能体协同下源—荷—储资源的状态交互与组合调节潜力，形成虚拟电厂整体可调容量和综合响应能力的协同表征结果。")
    add_subtitle(doc, "（3）面向多元市场调节需求的虚拟电厂资源多能力维度自监督智能分级分类方法研究")
    add_paragraph(doc, "研究电能量、辅助服务、需求响应等市场场景对资源能力的差异化要求，构建响应速度、持续性、可用容量、可靠性、经济性和安全约束等多能力维度指标体系；研究基于自监督学习、对比学习和无监督聚类的资源关键特征提取与能力层级识别方法，实现海量资源能力等级的自适应划分；构建资源—市场适配度评估和能力匹配校核机制，在物理、运行和协同约束下形成面向不同市场场景的智能分级分类结果。")

    add_paragraph(doc, "2.2 实施方案", "Heading 2")
    add_paragraph(doc, "课题实施遵循“前期调研与数据治理—行为因素分析与时序特征提取—意愿和能力协同建模—智能分级分类与市场适配验证”的总体路径。研究过程中统一资源分类、调节方向、数据粒度和评价口径，形成可追溯的数据字典和特征库；在此基础上将统计分析、因果推断、行为经济学建模、深度表示学习与多智能体协同分析有机衔接，逐步形成可用于虚拟电厂资源聚合与运营决策的能力画像。")
    add_subtitle(doc, "（1）资源行为影响因素与关键调节时序特征实施路径")
    add_paragraph(doc, "首先开展政策规则、市场场景、资源类型和运行数据的前期调研，明确资源主数据、实时运行状态、市场信号、外部环境、用户行为和调节事件等数据主题。随后，围绕资源参与、申报、执行和恢复全过程建立影响因素矩阵，采用混合效应模型和广义线性模型识别资源个体差异、场景差异与时间效应；通过结构因果模型和敏感性分析分离关键因素的影响作用；结合相似度度量、典型日聚类和阶段划分方法，形成关键调节时序特征及多维行为特征库。")
    add_subtitle(doc, "（2）可调容量与响应能力分析实施路径")
    add_paragraph(doc, "在行为特征库基础上，建立主观调节意愿与客观动态能力双通道模型。主观意愿侧重点分析价格敏感度、风险偏好、绿色价值取向和历史履约反馈对参与决策的影响；客观能力侧依据设备参数、运行状态、物理边界及环境条件，刻画资源在给定时段内可提供的功率、电量、速度、持续性与恢复能力。进一步面向源—荷—储协同场景构建多智能体状态交互与协同评估机制，综合形成可信可调用能力。模型精度考核目标为不低于90%，具体评价对象、样本划分、误差指标和验证口径将以项目数据条件及后续统一要求为准。")
    add_subtitle(doc, "（3）资源智能分级分类实施路径")
    add_paragraph(doc, "面向不同市场的调节需求，首先构建资源多能力维度指标体系和静态基础分级规则；其次，利用自监督学习和无监督聚类挖掘资源历史行为与能力特征的内在结构，形成可随数据更新的动态能力分层；最后，建立资源能力与市场需求的适配关系，并引入物理约束、运行约束和协同约束进行匹配校核，输出资源所属能力等级、适用市场场景和调用建议。分类结果将为后续课题开展套餐匹配、资源聚合、申报优化与运行控制提供标准化输入。")

    add_paragraph(doc, "2.3 课题组织与分工", "Heading 2")
    add_paragraph(doc, "课题由国网能源研究院有限公司牵头，国网山东省电力公司负责项目层面的组织协调与应用支撑，清华大学参与理论方法、模型构建和算法研究。各参与单位按照研究任务建立资料共享、模型评审和成果校核机制，确保研究口径、数据字段、模型版本和阶段成果可追溯、可衔接。具体分工如下表所示。")
    org_table = clone_table(doc, original_tables[0])
    fill_organization_table(org_table)

    add_paragraph(doc, "三、预期目标和成果形式", "Heading 1")
    add_paragraph(doc, "3.1 预期目标", "Heading 2")
    add_paragraph(doc, "分析差异化市场环境下虚拟电厂多元异质资源参与系统运行行为的影响机理，提出基于时序表征学习的资源行为建模方法；融合行为经济学、绿色价值与深度表示学习，提出多智能体协同的虚拟电厂资源差异化可调容量与响应能力分析方法；攻克适配多元电力市场调节需求的虚拟电厂资源多能力维度自监督智能分级分类方法。")
    add_paragraph(doc, "3.2 成果形式", "Heading 2")
    add_paragraph(doc, "（1）构建虚拟电厂多元异质资源可调容量与响应能力特征模型，模型精度不小于90%。")
    add_paragraph(doc, "（2）申请发明专利1项，发表或录用核心期刊或三大检索论文1篇。")
    add_paragraph(doc, "（3）提交《虚拟电厂多元异质资源调节行为分析与智能分类方法》技术报告。")

    add_paragraph(doc, "四、进度安排", "Heading 1")
    add_paragraph(doc, "课题按照项目总体进度，分阶段推进前期调研、特征解耦、能力量化、智能分级和成果凝练等工作。各时间段的研究内容与阶段成果如下表所示。")
    schedule_table = clone_table(doc, original_tables[1])
    fill_schedule_table(schedule_table)

    add_update_fields(doc)
    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
