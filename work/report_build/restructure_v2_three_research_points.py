from pathlib import Path
import re
import shutil
import zipfile

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt


SRC = Path("技术报告-课题一v2.docx")
OUT = Path("outputs/reports/技术报告-课题一v2-三研究点重构版.docx")


HEADING_RENAMES = {
    "2 虚拟电厂多元异质资源行为影响因素分析技术研究": "2 研究点一：虚拟电厂多元资源行为影响因素分析与关键调节时序特征研究",
    "2.1 研究问题界定与技术定位": "2.1 研究定位：从行为影响因素到时序特征",
    "2.2 多元异质资源的行为差异与调节边界": "2.2 多元资源行为差异与调节边界",
    "2.3 市场环境与外部状态耦合影响": "2.3 市场信号、外部环境与运行状态耦合影响",
    "2.4 用户行为偏好与聚合控制因素": "2.4 用户偏好、授权机制与聚合控制因素",
    "2.5 可观测变量与分析方法": "2.5 可观测变量、关键时序特征与分析方法",
    "3 虚拟电厂资源调节意愿与动态调节能力影响机理模型研究": "3 研究点二：虚拟电厂资源可调容量与响应能力分析方法研究",
    "3.1 研究任务与总体模型框架": "3.1 研究任务与统一分析框架",
    "3.2 调节意愿结构与模型表达": "3.2 调节意愿、动态能力与可信可调用能力机理",
    "4.1 研究定位与建模对象": "3.3 容量分层、建模对象与数据特征工程",
    "4.3 分资源可调容量与响应能力建模": "3.4 分资源可调容量与响应能力建模",
    "4.4 主客观约束融合与聚合层能力建模": "3.5 主客观约束融合与聚合协同评估",
    "4.5 模型训练、精度评价与应用接口": "3.6 模型训练、精度评价与应用接口",
    "4.6 本章小结": "3.7 本章小结",
    "5 面向多元市场调节需求的资源智能分级分类方法研究": "4 研究点三：面向多元市场调节需求的虚拟电厂资源多能力维度自监督智能分级分类方法研究",
    "5.1 研究定位与分类目标": "4.1 研究定位与分类目标",
    "5.2 市场需求画像与资源能力特征体系": "4.2 市场需求画像与资源能力特征体系",
    "5.3 分级规则与智能分类模型": "4.3 多能力维度表征、自监督降维与分级规则",
    "5.4 市场适配、资源池构建与约束校核": "4.4 市场适配、资源池构建与约束校核",
    "5.5 分类效果验证与评价指标": "4.5 分类效果验证与评价指标",
    "5.6 本章小结": "4.6 本章小结",
    "6 多维行为特征库构建与数据治理方案": "5 多维行为特征库构建与数据治理方案",
    "6.1 研究内容概述": "5.1 研究内容概述",
    "6.2 数据架构设计": "5.2 数据架构设计",
    "6.3 核心主题表设计": "5.3 核心主题表设计",
    "6.4 特征计算与样本组织": "5.4 特征计算与样本组织",
    "6.5 数据对齐与质量控制": "5.5 数据对齐与质量控制",
    "7 模型验证方案与精度评价体系": "6 模型验证方案与精度评价体系",
    "7.1 精度目标与评价对象": "6.1 精度目标与评价对象",
    "7.2 验证数据集设计": "6.2 验证数据集设计",
    "7.3 指标体系与计算口径": "6.3 指标体系与计算口径",
    "7.4 验证流程与基准模型": "6.4 验证流程与基准模型",
    "7.5 闭环优化机制": "6.5 闭环优化机制",
    "8 总结与展望": "7 总结与展望",
    "8.1 总结": "7.1 总结",
    "8.2 阶段性成果与创新点": "7.2 阶段性成果与创新点",
    "8.3 后续工作展望": "7.3 后续工作展望",
}


DELETE_HEADING_SECTIONS = {
    # The old chapter 3 summary is removed because chapter 3 now absorbs the
    # capacity and response-capability modeling material that used to be chapter 4.
    "3.6 本章小结",
}


DELETE_HEADINGS_ONLY = {
    "3.3 动态调节能力结构与典型资源机理",
    "3.4 意愿能力耦合与可信可调用能力",
    "3.5 实际响应、反馈机制与模型验证",
    "4 虚拟电厂资源可调容量与响应能力特征建模方法研究",
    "4.2 基线定义、容量边界与数据特征工程",
}


TOC_ENTRIES = [
    "摘要",
    "ABSTRACT",
    "1 概述",
    "2 研究点一：虚拟电厂多元资源行为影响因素分析与关键调节时序特征研究",
    "3 研究点二：虚拟电厂资源可调容量与响应能力分析方法研究",
    "4 研究点三：面向多元市场调节需求的虚拟电厂资源多能力维度自监督智能分级分类方法研究",
    "5 多维行为特征库构建与数据治理方案",
    "6 模型验证方案与精度评价体系",
    "7 总结与展望",
    "参考文献",
]


TEXT_REPLACEMENTS = {
    "报告首先从分布式光伏、储能、充电桩及充电站、工业可调负荷、商业楼宇空调等典型资源出发，分析市场信号、外部环境、物理属性、实时状态、用户行为、聚合控制和历史反馈对资源调节行为的作用机制；其次将资源响应行为拆分为调节意愿、动态调节能力、场景匹配、历史可靠度和安全校核等状态变量，提出可信可调用能力表达方式；再次围绕可调容量和响应能力特征建模，明确基线、容量边界、响应时延、爬坡速率、持续时间、调节精度、恢复时间、反弹风险和可用概率等关键特征；在此基础上，报告面向现货、需求响应、备用、调频、绿电消纳等多元市场需求，提出资源能力等级、市场适配类别、候选资源池构建和约束校核方法。":
    "报告围绕项目原始任务中的三个研究点展开。第一，面向分布式光伏、储能、充电桩及充电站、工业可调负荷、商业楼宇空调等典型资源，分析市场信号、外部环境、物理属性、实时状态、用户行为、聚合控制和历史反馈对资源调节行为的作用机制，并提取持续时间、爬坡速率、恢复间隔、反弹风险等关键调节时序特征。第二，将资源响应行为拆分为调节意愿、动态调节能力、场景匹配、历史可靠度和安全校核等状态变量，在此基础上统一开展可调容量与响应能力分析，明确基线、容量边界、响应时延、爬坡速率、持续时间、调节精度、恢复时间、反弹风险和可用概率等关键特征。第三，面向现货、需求响应、备用、调频、绿电消纳等多元市场需求，形成资源多能力维度自监督表征、能力等级划分、市场适配分类、候选资源池构建和约束校核方法。",
    "报告构建了“影响因素识别—调节意愿与动态能力机理建模—可调容量与响应能力特征建模—资源智能分级分类—数据治理与模型验证”的完整技术链条。":
    "报告构建了“行为影响因素与关键时序特征识别—可调容量与响应能力分析—多能力维度自监督智能分级分类—数据治理与模型验证”的完整技术链条。",
    "第2章重点研究多元异质资源行为影响因素，第3章研究调节意愿与动态调节能力影响机理，第4章研究可调容量与响应能力特征建模方法，第5章研究面向多元市场需求的资源智能分级分类方法。":
    "第2章对应研究点一，重点研究多元资源行为影响因素分析与关键调节时序特征；第3章对应研究点二，将调节意愿、动态调节能力、可调容量和响应能力统一纳入资源能力分析方法；第4章对应研究点三，研究面向多元市场调节需求的资源多能力维度自监督智能分级分类方法。",
    "本报告重点围绕四项研究任务展开。第一，研究虚拟电厂多元异质资源行为影响因素分析技术，回答哪些因素影响资源是否参与、能够调多少以及能否稳定执行。第二，研究虚拟电厂资源调节意愿与动态调节能力影响机理模型，回答主观意愿和客观能力如何共同决定实际响应。第三，研究虚拟电厂资源可调容量与响应能力特征建模方法，回答如何计算资源在不同时间和市场场景下的可调用能力。第四，研究面向多元市场调节需求的资源智能分级分类方法，回答如何根据市场需求将资源划分为不同能力等级和适配类别。":
    "本报告重点围绕三个研究点展开。第一，研究虚拟电厂多元资源行为影响因素分析与关键调节时序特征，回答哪些因素影响资源是否参与、能够调多少、能否稳定执行，以及历史响应曲线中哪些时序特征最能代表资源行为。第二，研究虚拟电厂资源可调容量与响应能力分析方法，回答主观调节意愿、客观动态能力、容量边界、响应速度、持续时间、可靠度和安全约束如何共同决定可信可调用能力。第三，研究面向多元市场调节需求的资源多能力维度自监督智能分级分类方法，回答如何根据多元市场任务要求，将资源划分为不同能力等级、适配类别和候选资源池。",
}


PARAGRAPH_REPLACEMENTS = {
    "虚拟电厂资源调节意愿与动态调节能力影响机理模型研究，是将第二章“影响因素清单”转化为可解释、可计算、可验证模型的关键环节。在虚拟电厂运营中，资源未达到预期响应并不一定意味着资源没有调节潜力，可能是用户不愿意开放能力，也可能是资源当前状态不满足调节要求，还可能是资源具备能力但不匹配具体市场任务的速度、持续时间、精度或安全约束。因此，本章的核心任务是把资源响应行为拆解为“调节意愿、动态调节能力、场景匹配、历史可靠度、安全校核”五个相互关联的状态变量，建立从影响因素到可信可调用能力的机理链条。":
    "研究点二不再把“调节意愿与动态调节能力机理”和“可调容量与响应能力特征建模”割裂为两个独立环节，而是将二者统一为资源能力分析方法。第二章识别了影响资源行为的市场、环境、状态、用户和控制因素，本章进一步回答这些因素如何转化为可计算的容量边界、响应速度、持续时间、可靠度和市场可调用能力。在虚拟电厂运营中，资源未达到预期响应并不一定意味着资源没有调节潜力，可能是用户不愿意开放能力，也可能是资源当前状态不满足调节要求，还可能是资源具备能力但不匹配具体市场任务的速度、持续时间、精度或安全约束。因此，本章以“愿不愿调、能不能调、能调多少、能否满足市场任务”为主线，建立从行为机理到工程化能力评估的统一框架。",
    "本章所说的调节意愿，是资源所有者或运营主体在特定市场场景下愿意参与调节、愿意开放容量、愿意持续响应的综合行为倾向；动态调节能力，是资源在某一时刻受物理属性、实时状态、外部环境和业务安全边界共同约束后能够实际提供的功率、电量、时间和可靠性边界。二者不能互相替代：用户非常愿意参与但车辆即将离站、储能SOC不足或工业产线处于关键工序时，无法形成有效响应；设备具备能力但用户未授权、收益不足或担心业务影响时，也不能直接纳入市场可交易能力。":
    "本章所说的调节意愿，是资源所有者或运营主体在特定市场场景下愿意参与调节、愿意开放容量、愿意持续响应的综合行为倾向；动态调节能力，是资源在某一时刻受物理属性、实时状态、外部环境和业务安全边界共同约束后能够实际提供的功率、电量、时间和可靠性边界；可调容量和响应能力，则是将上述主客观因素进一步落到功率、电量、时延、爬坡、持续、恢复、精度和可用概率等可评价指标上。三者不是并列堆叠关系，而是从行为原因、能力边界到模型输出的递进关系。",
    "虚拟电厂资源可调容量与响应能力特征建模，是把前两章的影响因素分析和机理模型转化为可计算模型输出的核心环节。第二章回答“哪些因素影响资源行为”，第三章回答“意愿与能力如何共同形成可信可调用能力”，本章进一步回答“如何把这些因素转化为模型输入、如何计算资源在某一时刻和某一市场场景下可调多少、能响应多快、能持续多久、可信度有多高”。因此，本章不是重复讨论调节意愿和动态能力的机理，而是围绕特征工程、容量边界、响应能力向量、资源专属模型、聚合修正和精度验证建立工程化建模方法。":
    "在统一分析框架下，可调容量与响应能力特征建模是研究点二的工程化落点。前文已经说明资源响应由意愿、能力、场景匹配、可靠度和安全校核共同决定，本节进一步将这些变量转化为模型输入和模型输出，回答资源在某一时刻、某一时间窗口和某一市场场景下可调多少、能响应多快、能持续多久、可信度有多高。由此，调节意愿和动态能力不再停留在概念层面，而是进入基线计算、容量分层、响应能力向量、资源专属模型、聚合修正和精度验证等可实施环节。",
    "本章建模对象包括两类输出。第一类是可调容量特征，主要描述资源在给定时间窗口内的向上/向下调节功率边界和可调电量边界；第二类是响应能力特征，主要描述资源从接收指令到形成有效响应的时延、爬坡速率、持续时间、跟踪精度、恢复时间、反弹风险和可用概率。二者共同构成后续智能分级分类的基础特征，也是项目提出“模型精度不低于90%”要求的主要评价对象。":
    "本章建模对象包括两类输出。第一类是可调容量特征，主要描述资源在给定时间窗口内的向上/向下调节功率边界和可调电量边界；第二类是响应能力特征，主要描述资源从接收指令到形成有效响应的时延、爬坡速率、持续时间、跟踪精度、恢复时间、反弹风险和可用概率。二者共同构成第三个研究点中资源多能力维度自监督分级分类的基础特征，也是项目提出“模型精度不低于90%”要求的主要评价对象。",
    "本章围绕虚拟电厂资源可调容量与响应能力特征建模，提出了从基线定义、容量分层、响应能力向量、资源专属模型、主客观约束融合、聚合层修正到精度评价和应用接口的建模方法。与只给出单一可调容量数值相比，本章更强调能力向量、场景匹配和可信度修正，能够更好适配现货、需求响应、备用和辅助服务等多市场任务。该方法将第二章的影响因素和第三章的意愿能力机理转化为可计算、可验证、可接入后续分类模型的工程化输出，为第六章特征库建设和第七章模型验证提供了直接对象。":
    "本章围绕虚拟电厂资源可调容量与响应能力分析方法，形成了从调节意愿识别、动态能力机理、容量分层、基线定义、响应能力向量、资源专属模型、主客观约束融合、聚合层修正到精度评价和应用接口的完整链条。与只给出单一可调容量数值相比，本章更强调能力向量、场景匹配和可信度修正，能够更好适配现货、需求响应、备用和辅助服务等多市场任务。本章成果将研究点一的影响因素和关键时序特征转化为可计算、可验证、可接入后续分类模型的工程化输出，并直接支撑研究点三的资源多能力维度自监督智能分级分类。",
    "资源智能分级分类不是简单把资源贴上“好、中、差”标签，而是要回答“什么资源适合什么市场、在什么时间尺度下适合什么任务、以多大能力参与更可靠”。":
    "资源多能力维度自监督智能分级分类不是简单把资源贴上“好、中、差”标签，而是要回答“什么资源适合什么市场、在什么时间尺度下适合什么任务、以多大能力参与更可靠”。",
    "表2表明，光伏、储能、充电站、工业负荷和楼宇空调虽然都可以纳入虚拟电厂，但其可调能力来源和限制因素完全不同。正是这种差异，决定了第三章需要区分调节意愿与动态能力，第四章需要建立分资源能力模型，第五章需要面向市场需求进行智能分级分类。":
    "表2表明，光伏、储能、充电站、工业负荷和楼宇空调虽然都可以纳入虚拟电厂，但其可调能力来源和限制因素完全不同。正是这种差异，决定了研究点二需要同时处理调节意愿、动态能力、分资源能力模型和可调容量边界，研究点三则需要在上述能力特征基础上面向市场需求进行智能分级分类。",
    "综上，虚拟电厂多元异质资源行为影响因素分析的关键在于把“资源有什么能力”进一步细化为“在什么市场场景、什么外部条件、什么实时状态、什么用户约束下能够释放何种能力”。本章从市场信号、资源物理属性、实时运行状态、用户行为偏好、聚合控制条件和历史响应反馈六个方面构建影响因素体系，并提出面向后续建模的变量化表达。该部分成果将直接支撑第三章调节意愿与动态调节能力影响机理建模、第四章可调容量与响应能力特征建模以及第五章面向多元市场需求的资源智能分级分类方法研究。":
    "综上，虚拟电厂多元资源行为影响因素分析与关键调节时序特征研究的关键，在于把“资源有什么能力”进一步细化为“在什么市场场景、什么外部条件、什么实时状态、什么用户约束下能够释放何种能力”。本章从市场信号、资源物理属性、实时运行状态、用户行为偏好、聚合控制条件和历史响应反馈六个方面构建影响因素体系，并提出面向后续建模的变量化表达。该部分成果将直接支撑研究点二的可调容量与响应能力分析，以及研究点三的资源多能力维度自监督智能分级分类。",
    "本项目已经在多维行为特征库数据字典中设计了资源主数据、资源运行状态时序、外部环境时序、市场信号、用户行为、调节事件、调节结果和行为特征等主题表。第四章的建模方法应明确这些主题表如何进入模型。":
    "本项目已经在多维行为特征库数据字典中设计了资源主数据、资源运行状态时序、外部环境时序、市场信号、用户行为、调节事件、调节结果和行为特征等主题表。研究点二的建模方法应明确这些主题表如何进入模型。",
}


def set_paragraph_text(paragraph, text, style_name=None):
    if style_name:
        paragraph.style = style_name
    paragraph.clear()
    run = paragraph.add_run(text)
    run.font.name = "宋体"
    run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "宋体")
    if paragraph.style and paragraph.style.name.startswith("Heading"):
        run.font.name = "黑体"
        run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "黑体")


def delete_paragraph(paragraph):
    element = paragraph._element
    element.getparent().remove(element)
    paragraph._p = paragraph._element = None


def delete_section_body(doc, heading_text):
    paragraphs = list(doc.paragraphs)
    start = None
    for idx, paragraph in enumerate(paragraphs):
        if paragraph.text.strip() == heading_text:
            start = idx
            break
    if start is None:
        return 0
    start_level = int(paragraphs[start].style.name.split()[-1])
    end = len(paragraphs)
    for idx in range(start + 1, len(paragraphs)):
        style = paragraphs[idx].style.name if paragraphs[idx].style else ""
        if style.startswith("Heading"):
            level = int(style.split()[-1])
            if level <= start_level:
                end = idx
                break
    count = 0
    for paragraph in paragraphs[start:end]:
        delete_paragraph(paragraph)
        count += 1
    return count


def insert_after(paragraph, text, style_name="Normal"):
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    p = paragraph._parent.paragraphs[-1]
    # Re-resolve the newly inserted paragraph by scanning for the XML object.
    for candidate in paragraph._parent.paragraphs:
        if candidate._p is new_p:
            p = candidate
            break
    set_paragraph_text(p, text, style_name)
    p.paragraph_format.first_line_indent = Pt(24)
    p.paragraph_format.line_spacing = 1.25
    p.paragraph_format.space_after = Pt(6)
    return p


def apply_text_replacements(doc):
    changed = 0
    for paragraph in doc.paragraphs:
        text = paragraph.text
        stripped = text.strip()
        if stripped in PARAGRAPH_REPLACEMENTS:
            set_paragraph_text(paragraph, PARAGRAPH_REPLACEMENTS[stripped])
            changed += 1
            continue
        new_text = text
        for old, new in TEXT_REPLACEMENTS.items():
            new_text = new_text.replace(old, new)
        if new_text != text:
            set_paragraph_text(paragraph, new_text)
            changed += 1
    return changed


def rename_headings(doc):
    renamed = 0
    deleted_heading_only = 0
    for paragraph in list(doc.paragraphs):
        text = paragraph.text.strip()
        style = paragraph.style.name if paragraph.style else ""
        if style.startswith("Heading") and text in DELETE_HEADINGS_ONLY:
            delete_paragraph(paragraph)
            deleted_heading_only += 1
            continue
        if style.startswith("Heading") and text in HEADING_RENAMES:
            set_paragraph_text(paragraph, HEADING_RENAMES[text], style)
            renamed += 1
    return renamed, deleted_heading_only


def restore_static_toc(doc):
    paragraphs = list(doc.paragraphs)
    toc_idx = None
    first_chapter_idx = None
    for idx, paragraph in enumerate(paragraphs):
        text = paragraph.text.strip()
        style = paragraph.style.name if paragraph.style else ""
        if style == "Heading 1" and text == "目录":
            toc_idx = idx
        elif toc_idx is not None and style == "Heading 1" and text.startswith("1 "):
            first_chapter_idx = idx
            break
    if toc_idx is None or first_chapter_idx is None:
        return 0
    for paragraph in list(doc.paragraphs)[toc_idx + 1:first_chapter_idx]:
        delete_paragraph(paragraph)
    first_chapter = next(
        p for p in doc.paragraphs
        if (p.style.name if p.style else "") == "Heading 1" and p.text.strip().startswith("1 ")
    )
    for entry in reversed(TOC_ENTRIES):
        p = first_chapter.insert_paragraph_before(entry)
        p.style = "Normal"
        p.paragraph_format.first_line_indent = Pt(0)
        p.paragraph_format.space_after = Pt(3)
        if p.runs:
            run = p.runs[0]
            run.font.name = "宋体"
            run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "宋体")
            run.font.size = Pt(12)
    return len(TOC_ENTRIES)


def fix_formula_garbles(docx_path):
    tmp = docx_path.with_suffix(".tmp")
    with zipfile.ZipFile(docx_path, "r") as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                text = data.decode("utf-8")
                # Known mojibake from Word equation conversion. Restrict Phi
                # fixes to math text so normal Chinese words such as "实施"
                # remain untouched.
                def fix_math_text(match):
                    content = match.group(1)
                    content = content.replace("蟿", "τ")
                    content = content.replace("施", "Φ")
                    content = content.replace("脑", "×")
                    return f"<m:t>{content}</m:t>"

                text = re.sub(r"<m:t>(.*?)</m:t>", fix_math_text, text)
                text = re.sub(
                    r"<m:t>R_i\(t,H\)=\[.*?ramp_i, dur_i, acc_i, rec_i, prob_i\]</m:t>",
                    "<m:t>R_i(t,H)=[τ_i, ramp_i, dur_i, acc_i, rec_i, prob_i]</m:t>",
                    text,
                    count=1,
                )
                data = text.encode("utf-8")
            zout.writestr(item, data)
    tmp.replace(docx_path)


def inspect(docx_path):
    doc = Document(docx_path)
    headings = []
    counts = {}
    toc_entries = 0
    in_toc = False
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        style = paragraph.style.name if paragraph.style else ""
        if style == "Heading 1" and text == "目录":
            in_toc = True
            continue
        if in_toc and style == "Heading 1" and text.startswith("1 "):
            in_toc = False
        if in_toc and text:
            toc_entries += 1
        if style.startswith("Heading") and text:
            headings.append((style, text))
            if style == "Heading 1" and text[:1].isdigit():
                counts[text[0]] = counts.get(text[0], 0) + 1
    data = zipfile.ZipFile(docx_path).read("word/document.xml").decode("utf-8")
    print(f"output={docx_path}")
    print(f"toc_entries={toc_entries}")
    print(f"chapter_heading_counts={counts}")
    print(f"oMath={data.count('<m:oMath')}")
    print(f"garbled_known_math={data.count('蟿')},{data.count('<m:t>施')},{data.count('<m:t>脑')}")
    print("research_headings=")
    for style, text in headings:
        if style == "Heading 1" and text.startswith(("2 ", "3 ", "4 ")):
            print(text)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC, OUT)
    doc = Document(OUT)

    removed_sections = 0
    for heading in DELETE_HEADING_SECTIONS:
        removed_sections += delete_section_body(doc, heading)

    renamed, deleted_heading_only = rename_headings(doc)
    text_changed = apply_text_replacements(doc)

    # Add a short bridge before the former chapter-4 modeling material, now part
    # of research point two.
    for paragraph in doc.paragraphs:
        if paragraph.text.strip() == "3.3 容量分层、建模对象与数据特征工程":
            insert_after(
                paragraph,
                "为避免研究内容在“行为机理”和“工程建模”之间断裂，本节把容量分层、基线定义和数据特征工程直接放入研究点二内部处理。这样，调节意愿、动态能力和响应特征不再是前后割裂的描述，而是共同服务于同一个能力分析模型：先判断资源是否愿意开放能力，再判断资源在当前状态下是否具备能力，最后将其转化为可用于市场申报、资源组合和履约校核的容量与响应能力向量。",
            )
            break

    restore_static_toc(doc)
    doc.save(OUT)
    fix_formula_garbles(OUT)
    inspect(OUT)
    print(f"renamed={renamed}, deleted_heading_only={deleted_heading_only}, removed_section_paragraphs={removed_sections}, text_changed={text_changed}")


if __name__ == "__main__":
    main()
