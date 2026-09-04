from copy import deepcopy
from pathlib import Path
import os
import tempfile
import zipfile
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph


TEMPLATE = Path(r"D:\wechat\cunchu\xwechat_files\wxid_bwerc1yl4z4k22_d623\temp\RWTemp\2026-07\8115529b7fa47ec7594d7a371c4817cc\课题3实施方案.docx")
FEASIBILITY = Path(r"D:\myDocu\project_postg\VPP_program\01_项目依据\101_可研_国网山东电力-基于新型电力负荷管理系统的虚拟电厂市场化运营服务支撑技术及应用.docx")
OUT = Path(r"D:\myDocu\project_postg\VPP_program\outputs\reports\课题一实施方案.docx")


def replace_in_existing_paragraph(paragraph, text, bold=None):
    """Replace visible text while retaining the first original run's direct formatting."""
    p = paragraph._p
    runs = paragraph.runs
    if runs:
        retained = runs[0]
        retained.text = text
        keep = retained._r
        for child in list(p):
            if child.tag != qn("w:pPr") and child is not keep:
                p.remove(child)
        if bold is not None:
            retained.bold = bold
    else:
        run = paragraph.add_run(text)
        if bold is not None:
            run.bold = bold


def replace_full_paragraph(paragraph, text):
    """Use only for the two damaged TOC field-display entries."""
    p = paragraph._p
    run_properties = deepcopy(paragraph.runs[0]._r.rPr) if paragraph.runs and paragraph.runs[0]._r.rPr is not None else None
    for child in list(p):
        if child.tag != qn("w:pPr"):
            p.remove(child)
    run = paragraph.add_run(text)
    if run_properties is not None:
        run._r.insert(0, run_properties)


def remove_paragraph(paragraph):
    parent = paragraph._p.getparent()
    parent.remove(paragraph._p)


def insert_like_after(anchor, prototype, text, bold=False):
    """Insert a paragraph that inherits an existing body paragraph's direct formatting."""
    clone = deepcopy(prototype._p)
    anchor._p.addnext(clone)
    paragraph = Paragraph(clone, anchor._parent)
    replace_in_existing_paragraph(paragraph, text, bold=bold)
    return paragraph


def set_cell_text(cell, text):
    replace_in_existing_paragraph(cell.paragraphs[0], text)
    for paragraph in cell.paragraphs[1:]:
        replace_in_existing_paragraph(paragraph, "")


def update_fields(doc):
    settings = doc.settings.element
    update = settings.find(qn("w:updateFields"))
    if update is None:
        update = OxmlElement("w:updateFields")
        settings.append(update)
    update.set(qn("w:val"), "true")


def replace_template_figure_blobs():
    """Retain original template picture containers while replacing their EMF content."""
    replacements = {
        "word/media/image2.emf": "word/media/image20.emf",  # Figure 4-8, overall route
        "word/media/image4.emf": "word/media/image21.emf",  # Figure 4-9, research point 1
        "word/media/image5.emf": "word/media/image22.emf",  # Figure 4-10, research point 2
        "word/media/image3.emf": "word/media/image23.emf",  # Figure 4-11, research point 3
    }
    with zipfile.ZipFile(FEASIBILITY, "r") as source_zip:
        source_blobs = {target: source_zip.read(source) for target, source in replacements.items()}
    fd, temp_path = tempfile.mkstemp(suffix=".docx", dir=OUT.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(OUT, "r") as old_zip, zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as new_zip:
            for info in old_zip.infolist():
                new_zip.writestr(info, source_blobs.get(info.filename, old_zip.read(info.filename)))
        os.replace(temp_path, OUT)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def restore_toc_format(doc):
    """Restore the template's exact TOC paragraph and run formatting after text replacement."""
    source_doc = Document(TEMPLATE)
    for index in range(20, 34):
        source_p = source_doc.paragraphs[index]
        target_p = doc.paragraphs[index]
        source_ppr = source_p._p.pPr
        target_ppr = target_p._p.pPr
        if target_ppr is not None:
            target_p._p.remove(target_ppr)
        if source_ppr is not None:
            target_p._p.insert(0, deepcopy(source_ppr))
        source_runs = source_p.runs
        for run_index, target_run in enumerate(target_p.runs):
            source_run = source_runs[min(run_index, len(source_runs) - 1)] if source_runs else None
            if source_run is None or source_run._r.rPr is None:
                continue
            target_rpr = target_run._r.rPr
            if target_rpr is not None:
                target_run._r.remove(target_rpr)
            target_run._r.insert(0, deepcopy(source_run._r.rPr))


def fill_organization_table(table):
    values = [
        ["序号", "课题设置", "项目牵头单位", "课题牵头单位", "课题负责人", "合作单位", "合作单位分工"],
        ["课题1", "虚拟电厂多元异质资源调节行为分析与智能分类方法", "国网山东省电力公司", "国网能源研究院有限公司", "吴潇雨\n李龙", "国网能源研究院有限公司", "（1）融合行为经济学、绿色价值与多智能体协同的虚拟电厂资源可调容量与响应能力分析方法研究\n（2）面向多元市场调节需求的虚拟电厂资源多能力维度自监督智能分级分类方法研究"],
        ["课题1", "虚拟电厂多元异质资源调节行为分析与智能分类方法", "国网山东省电力公司", "国网能源研究院有限公司", "吴潇雨\n李龙", "清华大学", "（1）差异化市场环境下虚拟电厂多元资源行为影响因素分析与关键调节时序特征研究\n（2）融合行为经济学、绿色价值与多智能体协同的虚拟电厂资源可调容量与响应能力分析方法研究\n（3）面向多元市场调节需求的虚拟电厂资源多能力维度自监督智能分级分类方法研究"],
    ]
    for row, row_values in zip(table.rows, values):
        for cell, value in zip(row.cells, row_values):
            set_cell_text(cell, value)


def fill_schedule_table(table):
    values = [
        ["序号", "时间段", "内         容"],
        ["1", "2026.03", "研究内容：\n1. 针对课题开展前期调研工作，收集、整理相关资料及数据；\n2. 明确研究目标，确定研究思路，编制课题实施方案。\n阶段成果：\n1. 形成课题实施方案。"],
        ["2", "2026.04 - 2026.06", "研究内容：\n1. 研究混合效应模型与广义线性模型量化差异化市场环境对资源行为的影响；\n2. 建立涵盖市场信号、环境参数与物理属性的资源多维行为特征库基础架构。\n阶段成果：\n1. 提出虚拟电厂资源调节意愿与动态调节能力的影响机理模型。"],
        ["3", "2026.07 - 2026.09", "研究内容：\n1. 研发基于结构因果模型与因果图学习的驱动因素解耦方法；\n2. 识别资源调节过程中的非线性特征、关键响应阈值区间与敏感性。\n阶段成果：\n1. 提出资源调节行为关键驱动因素解耦与异质资源调节决策敏感性特征模型。"],
        ["4", "2026.10 - 2026.12", "研究内容：\n1. 提取各类资源的基准运行曲线与典型调节模式；\n2. 开展资源调节全周期特征解构，识别持续、波动与恢复等阶段性时序特征。\n阶段成果：\n1. 提出资源调节全周期调节特征演化规律特征提取方案。"],
        ["5", "2027.01 - 2027.03", "研究内容：\n1. 研究融合价格敏感性、用能偏好与绿色价值取向的多源行为因子；\n2. 引入行为经济学前景理论与离散选择模型，刻画用户在风险与不确定性下的参与偏好。\n阶段成果：\n1. 提出融合行为经济学的主观意愿调节方法。"],
        ["6", "2027.04 - 2027.06", "研究内容：\n1. 研究资源客观物理调节能力特征映射模型；\n2. 开展多智能体协同的源—荷—储交互分析，评估复杂场景下的组合调节潜力。\n阶段成果：\n1. 提出资源调节特征高维映射与时序响应能力建模方法；\n2. 提出虚拟电厂整体可调容量与综合响应特性的协同能力表征方案；\n3. 申请相关发明专利1项。"],
        ["7", "2027.07 - 2027.09", "研究内容：\n1. 解析多元市场需求，研究响应速度、持续性等多维能力指标分级分类方法；\n2. 运用自监督学习与无监督聚类算法，挖掘海量资源特征的潜在分布。\n阶段成果：\n1. 提出虚拟电厂资源多维度静态基础分级分类方法；\n2. 提出基于自监督学习与无监督聚类算法的智能分级分类方法。"],
        ["8", "2027.10 - 2027.12", "研究内容：\n1. 构建市场适配度评估模型，研究资源能力与市场需求向量的匹配指数；\n2. 引入物理、运行和协同约束进行匹配校核。\n阶段成果：\n1. 提出资源市场适配度评估与能力匹配校核方法。"],
        ["9", "2028.01 - 2028.02", "研究内容：\n1. 整理核心技术成果，撰写高水平学术论文与技术报告；\n2. 完成知识产权申报与结题验收准备。\n阶段成果：\n1. 发表或录用核心期刊或三大检索论文1篇；\n2. 提交《虚拟电厂多元异质资源调节行为分析与智能分类方法》技术报告。"],
    ]
    for row, row_values in zip(table.rows, values):
        for cell, value in zip(row.cells, row_values):
            set_cell_text(cell, value)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = Document(TEMPLATE)
    p = list(doc.paragraphs)

    # Retain every original paragraph position and its direct typography.
    replacements = {
        6: "虚拟电厂多元异质资源调节行为分析",
        7: "与智能分类方法",
        8: "实施方案",
        9: "Research and Implementation Plan for Regulation Behavior Analysis and Intelligent Classification of Diverse Heterogeneous Virtual Power Plant Resources",
        14: "国网能源研究院有限公司",
        15: "国网山东省电力公司",
        16: "清华大学",
        17: "2026年7月",
        35: "一、目的和意义",
        36: "1.1 研究背景",
        37: "虚拟电厂通过聚合分布式电源、储能、可调负荷和电动汽车等资源参与电力系统运行与市场交易，是提升需求侧灵活性和支撑新型电力系统建设的重要组织形态。随着多元电力市场逐步完善，虚拟电厂需要面向电能量、调频、爬坡、需求响应等不同场景开展资源调节，资源的响应速度、持续时间、可靠性和经济性成为影响市场参与成效的关键因素。",
        38: "多元异质资源在设备特性、实时状态、外部环境、用户偏好和控制方式上存在明显差异。光伏受辐照和天气影响，储能受荷电状态和寿命约束，可调负荷和充电资源则同时受到生产计划、出行需求、舒适度和用户授权等约束。市场价格、补偿机制、调用频率、考核规则和通知时间的变化，又会改变资源的参与意愿与实际执行质量。仅依赖额定容量或静态标签难以反映资源在特定场景下的真实可调用能力。",
        39: "课题一面向虚拟电厂资源侧的基础认知问题，围绕“资源是否愿意参与、当前能够调多少、能够持续多久、适合参与何种市场”开展研究，建立覆盖行为影响因素、关键调节时序特征、可调容量、响应能力及市场适配性的统一框架，为项目后续的套餐设计、市场运营优化、阻塞管理和示范应用提供资源特征与能力边界支撑。",
        40: "1.2 研究必要性、目的和意义",
        41: "1.2.1 研究必要性",
        42: "研究必要性：面向多元市场的资源实际可调用能力，必须同时覆盖参与意愿、动态物理边界和履约可信度。",
        43: "因此，需要从资源行为、主观意愿和客观能力协同角度开展研究，形成可追溯、可计算、可验证的资源能力画像，为虚拟电厂的资源准入、聚合编组、能力申报、履约评估及市场化运营提供统一依据。",
        44: "1.2.2 研究目的",
        45: "研究目的：构建从行为影响因素识别、能力量化到市场适配分类的虚拟电厂资源认知方法体系。",
        46: "1.2.3 研究意义",
        47: "研究意义：形成可解释、可计算、可迭代的资源能力画像，为虚拟电厂市场化运营提供统一的资源侧基础。",
        49: "二、研究内容和实施方案",
        50: "2.1 研究内容",
        51: "本课题围绕“特征解耦、能力量化、智能分级”三条主线展开，形成由资源行为认知到市场应用的递进式研究体系。研究对象包括分布式电源、储能、可调负荷和充电设施等典型资源，重点关注资源在多元市场和复杂运行场景下的实际可调用能力。课题一总体技术路线如图2-1所示。",
        53: "图2-1 课题一总体技术路线",
        54: "（1）差异化市场环境下虚拟电厂多元资源行为影响因素分析与关键调节时序特征研究",
        55: "研究多元市场激励信号与用户主观行为特征之间的作用机理，分析价格、补偿、考核、调用频率、持续时间和通知时间等因素对资源调节意愿与动态调节能力的影响路径；构建基于混合效应模型、广义线性模型、结构因果模型和因果图学习的关键驱动因素解耦方法，分离量化多维因素对异质资源调节决策的影响；研究资源调节全周期的持续、波动、恢复等阶段性行为模式，提取基准曲线、最大持续时间、最大爬坡率和恢复间隔等关键时序特征，构建多维行为特征库。",
        56: "（2）融合行为经济学、绿色价值与多智能体协同的虚拟电厂资源可调容量与响应能力分析方法研究",
        57: "研究融合价格敏感度、用能偏好、风险偏好和绿色价值取向的多源行为因子建模方法，利用前景理论与离散选择机制刻画用户主观参与偏好；研究基于深度表示学习的资源调节特征高维映射与时序响应能力建模方法，对上下调功率、可调电量、响应时延、持续时间、恢复时间和跟踪精度等客观能力进行结构化表征；研究多智能体协同下源—荷—储资源的状态交互与组合调节潜力，形成虚拟电厂整体可调容量和综合响应能力的协同表征结果。",
        58: "（3）面向多元市场调节需求的虚拟电厂资源多能力维度自监督智能分级分类方法研究",
        59: "研究电能量、辅助服务、需求响应等市场场景对资源能力的差异化要求，构建响应速度、持续性、可用容量、可靠性、经济性和安全约束等多能力维度指标体系；研究基于自监督学习、对比学习和无监督聚类的资源关键特征提取与能力层级识别方法，实现海量资源能力等级的自适应划分；构建资源—市场适配度评估和能力匹配校核机制，在物理、运行和协同约束下形成面向不同市场场景的智能分级分类结果。",
        60: "2.2 实施方案",
        61: "课题实施遵循“前期调研与数据治理—行为因素分析与时序特征提取—意愿和能力协同建模—智能分级分类与市场适配验证”的总体路径。研究过程中统一资源分类、调节方向、数据粒度和评价口径，形成可追溯的数据字典和特征库；在此基础上将统计分析、因果推断、行为经济学建模、深度表示学习与多智能体协同分析有机衔接，逐步形成可用于虚拟电厂资源聚合与运营决策的能力画像。",
        64: "（1）资源行为影响因素与关键调节时序特征实施路径",
        65: "首先开展政策规则、市场场景、资源类型和运行数据的前期调研，明确资源主数据、实时运行状态、市场信号、外部环境、用户行为和调节事件等数据主题。随后，围绕资源参与、申报、执行和恢复全过程建立影响因素矩阵，采用混合效应模型和广义线性模型识别资源个体差异、场景差异与时间效应；通过结构因果模型和敏感性分析分离关键因素的影响作用；结合相似度度量、典型日聚类和阶段划分方法，形成关键调节时序特征及多维行为特征库，具体实施路径如图2-2所示。",
        67: "图2-2 研究内容1技术路线",
        68: "（2）可调容量与响应能力分析实施路径",
        69: "在行为特征库基础上，建立主观调节意愿与客观动态能力双通道模型。主观意愿侧重点分析价格敏感度、风险偏好、绿色价值取向和历史履约反馈对参与决策的影响；客观能力侧依据设备参数、运行状态、物理边界及环境条件，刻画资源在给定时段内可提供的功率、电量、速度、持续性与恢复能力。进一步面向源—荷—储协同场景构建多智能体状态交互与协同评估机制，综合形成可信可调用能力。模型精度考核目标为不低于90%，具体评价对象、样本划分、误差指标和验证口径将以项目数据条件及后续统一要求为准。具体实施路径如图2-3所示。",
        71: "图2-3 研究内容2技术路线",
        72: "（3）资源智能分级分类实施路径",
        73: "面向不同市场的调节需求，首先构建资源多能力维度指标体系和静态基础分级规则；其次，利用自监督学习和无监督聚类挖掘资源历史行为与能力特征的内在结构，形成可随数据更新的动态能力分层；最后，建立资源能力与市场需求的适配关系，并引入物理约束、运行约束和协同约束进行匹配校核，输出资源所属能力等级、适用市场场景和调用建议。分类结果将为后续课题开展套餐匹配、资源聚合、申报优化与运行控制提供标准化输入，具体实施路径如图2-4所示。",
        63: "图2-4 研究内容3技术路线",
        76: "2.3 课题组织与分工",
        77: "三、预期目标和成果形式",
        78: "3.1 预期目标",
        79: "分析差异化市场环境下虚拟电厂多元异质资源参与系统运行行为的影响机理，提出基于时序表征学习的资源行为建模方法；融合行为经济学、绿色价值与深度表示学习，提出多智能体协同的虚拟电厂资源差异化可调容量与响应能力分析方法；攻克适配多元电力市场调节需求的虚拟电厂资源多能力维度自监督智能分级分类方法。",
        80: "3.2 成果形式",
        81: "（1）构建虚拟电厂多元异质资源可调容量与响应能力特征模型，模型精度不小于90%。",
        82: "（2）申请发明专利1项，发表或录用核心期刊或三大检索论文1篇。",
        83: "（3）提交《虚拟电厂多元异质资源调节行为分析与智能分类方法》技术报告。",
        85: "四、进度安排",
    }
    # Keep regular body text regular; leave heading paragraphs under the template's original direct formatting.
    body_indices = {37, 38, 39, 43, 51, 55, 57, 59, 61, 65, 69, 73, 79, 81, 82, 83}
    normal_headings = {41, 44, 46, 54, 56, 58, 64, 68, 72}
    summary_indices = {42, 45, 47}
    for index, text in replacements.items():
        replace_in_existing_paragraph(
            p[index], text,
            bold=False if index in body_indices else (True if index in normal_headings or index in summary_indices else None),
        )

    replace_full_paragraph(p[24], "1.2.2 研究目的\t2")
    replace_full_paragraph(p[25], "1.2.3 研究意义\t2")

    # Add an explanatory paragraph after each bold one-sentence lead in Section 1.2.
    purpose_detail = insert_like_after(
        p[45], p[43],
        "本课题拟识别并解耦差异化市场环境、资源物理属性和用户行为等因素对调节行为的影响，提取关键调节时序特征；融合行为经济学、绿色价值与多智能体协同，形成资源可调容量与响应能力的综合表征；建立面向多元市场调节需求的多能力维度自监督智能分级分类方法，实现资源能力与市场场景的精准匹配。",
    )
    significance_detail = insert_like_after(
        p[47], p[43],
        "研究成果将形成“数据—特征—能力—分类—应用”的资源认知链条。一方面，可为虚拟电厂资源准入、聚合编组、能力申报和履约评估提供量化依据；另一方面，可向后续课题输出资源行为特征、能力边界和市场适配结果，支撑多元市场套餐优化、阻塞管理及智能运营服务模块的协同开发。",
    )
    insert_like_after(
        p[43], p[43],
        "在实际运行中，额定容量、申报容量与可稳定执行的响应容量之间往往存在差异。资源状态变化、调用频次增加、用户临时用能需求以及市场考核压力，均可能使资源在同一设备参数下呈现不同的响应结果。通过对影响因素及其相互作用进行系统分析，可减少静态容量评价带来的偏差，提升虚拟电厂资源调用的可靠性和可解释性。",
    )
    insert_like_after(
        purpose_detail, p[43],
        "围绕上述目标，课题将以统一数据口径和多维行为特征库为基础，将行为因素分析结果转化为可观测、可计算的模型变量；再将主观意愿、客观能力和协同关系映射为可信可调用能力；最后通过资源—市场适配评估输出分级分类结果。该技术路线既保证研究过程的逻辑递进，也为后续模型训练、参数校准和工程应用预留统一接口。",
    )
    insert_like_after(
        significance_detail, p[43],
        "从工程应用看，课题形成的数据字段、特征计算规则、能力标签和市场适配结果，可作为虚拟电厂运营服务支撑模块的基础输入，并与后续的套餐定价、资源聚合、市场申报和运行控制环节衔接。从研究方法看，课题将资源物理特性、用户行为和市场需求纳入同一分析框架，有助于提升资源分类结果的透明性、可复用性和持续迭代能力。",
    )

    # Expand the three implementation routes before their corresponding figures.
    route1_detail = insert_like_after(
        p[65], p[43],
        "在数据与验证层面，按照资源类型、市场场景和调节事件建立分层样本，统一时间粒度、调节方向和基线计算口径；针对缺失、异常和不同资源采样频率不一致等问题，形成数据质量校核与特征计算规则。模型输出以影响方向、作用强度、阈值区间和典型时序模式为核心，并通过跨场景对比和历史事件回放检验其稳定性，为后续能力建模提供可信输入。",
    )
    route2_detail = insert_like_after(
        p[69], p[43],
        "能力评估过程中，将物理约束模型与数据驱动模型结合：先依据额定功率、荷电状态、设备健康度、工艺边界等确定可行域，再利用历史响应结果修正可用容量、时延和跟踪精度。针对不同主体之间的协同关系，设置资源状态、激励信号、任务约束和履约反馈等交互变量，比较单资源能力与聚合能力的差异，并以预测误差、响应偏差和可用率等指标开展模型精度验证。",
    )
    route3_detail = insert_like_after(
        p[73], p[43],
        "分类结果除给出资源所属能力等级外，还应标注适用调节方向、推荐持续时间、可承受调用频次和主要风险约束。通过将电能量、辅助服务和需求响应等市场需求转化为统一的能力需求向量，计算资源—市场适配度；当资源实时状态、市场规则或历史履约表现发生变化时，按既定更新周期重新计算特征与分类结果，保障分类结果能够服务于动态聚合和精准调用。",
    )

    # Retain four original picture containers, and move the fourth to follow research point 3.
    route3_detail._p.addnext(p[62]._p)
    p[62]._p.addnext(p[63]._p)

    # Remove the unused duplicate image/caption pair and the fourth outcome item from the source template.
    for index in [74, 75, 84]:
        remove_paragraph(p[index])

    fill_organization_table(doc.tables[0])
    fill_schedule_table(doc.tables[1])
    restore_toc_format(doc)
    update_fields(doc)
    doc.save(OUT)
    replace_template_figure_blobs()
    print(OUT)


if __name__ == "__main__":
    main()
