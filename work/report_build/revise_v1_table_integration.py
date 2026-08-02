from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.table import Table
from docx.text.paragraph import Paragraph


SOURCE = Path("技术报告-课题一v1.docx")
OUTPUT = Path("outputs/reports/技术报告-课题一v1-表文衔接修正版.docx")


def set_font(paragraph, font_name="宋体", size_pt=12):
    for run in paragraph.runs:
        run.font.name = font_name
        run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), font_name)
        if paragraph.style.name == "Normal":
            run.font.size = Pt(size_pt)


def paragraph_before(element, parent, text, style="Normal", first_indent=True):
    new_p = OxmlElement("w:p")
    element.addprevious(new_p)
    paragraph = Paragraph(new_p, parent)
    paragraph.style = style
    paragraph.add_run(text)
    set_font(paragraph)
    paragraph.paragraph_format.space_after = Pt(6)
    paragraph.paragraph_format.line_spacing = 1.25
    if first_indent:
        paragraph.paragraph_format.first_line_indent = Pt(24)
    return paragraph


def paragraph_after(element, parent, text, style="Normal", first_indent=True):
    new_p = OxmlElement("w:p")
    element.addnext(new_p)
    paragraph = Paragraph(new_p, parent)
    paragraph.style = style
    paragraph.add_run(text)
    set_font(paragraph)
    paragraph.paragraph_format.space_after = Pt(6)
    paragraph.paragraph_format.line_spacing = 1.25
    if first_indent:
        paragraph.paragraph_format.first_line_indent = Pt(24)
    return paragraph


def delete_paragraph(paragraph):
    element = paragraph._element
    element.getparent().remove(element)
    paragraph._p = paragraph._element = None


def delete_range(doc, start_prefix, end_prefix):
    start = None
    end = None
    for idx, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if text.startswith(start_prefix):
            start = idx
        elif start is not None and text.startswith(end_prefix):
            end = idx
            break
    if start is None or end is None:
        return
    for para in list(doc.paragraphs[start:end]):
        delete_paragraph(para)


def replace_text_in_paragraphs(doc, replacements):
    for para in doc.paragraphs:
        text = para.text
        new_text = text
        for old, new in replacements.items():
            new_text = new_text.replace(old, new)
        if new_text != text:
            para.clear()
            para.add_run(new_text)
            set_font(para)
            if para.style.name == "Normal":
                para.paragraph_format.first_line_indent = Pt(24)
                para.paragraph_format.space_after = Pt(6)
                para.paragraph_format.line_spacing = 1.25


def find_paragraph(doc, startswith):
    for para in doc.paragraphs:
        if para.text.strip().startswith(startswith):
            return para
    raise ValueError(f"Paragraph not found: {startswith}")


def find_table(doc, first_cell):
    for table in doc.tables:
        if table.rows and table.rows[0].cells:
            text = " ".join(p.text.strip() for p in table.rows[0].cells[0].paragraphs if p.text.strip())
            if text == first_cell:
                return table
    raise ValueError(f"Table not found: {first_cell}")


def move_table_before(table: Table, paragraph: Paragraph):
    paragraph._p.addprevious(table._element)


def add_table_bridge(table: Table, intro: str, caption: str, analysis: str):
    paragraph_before(table._element, table._parent, intro)
    cap = paragraph_before(table._element, table._parent, caption, first_indent=False)
    cap.alignment = 1
    if cap.runs:
        cap.runs[0].bold = True
    paragraph_after(table._element, table._parent, analysis)


def remove_repeated_data_placeholders(doc):
    delete_range(doc, "2.8 真实数据支撑与后续替换口径", "2.9 本章小结")
    delete_range(doc, "3.9 真实数据支撑与后续替换口径", "3.10 本章小结")
    delete_range(doc, "5.9 真实数据支撑与后续替换口径", "5.10 本章小结")

    for para in list(doc.paragraphs):
        if "真实数据支撑与后续替换口径" in para.text:
            delete_paragraph(para)

    replace_text_in_paragraphs(
        doc,
        {
            "2.9 本章小结": "2.8 本章小结",
            "3.10 本章小结": "3.9 本章小结",
            "5.10 本章小结": "5.9 本章小结",
            "并提出面向后续建模的变量化表达和数据替换口径。": "并提出面向后续建模的变量化表达。", 
            "报告均保留替换口径，便于后续在获取真实数据后继续完善。": "报告均以验证方案和数据需求方式呈现，便于后续在获取真实数据后继续完善。", 
            "报告以模型框架、变量口径、数据需求、验证方案和后续替换口径为主": "报告以模型框架、变量口径、数据需求、验证方案和数据补充接口为主",
            "reserving clear replacement interfaces for future real project data": "leaving clear interfaces for future calibration with real project data",
            "报告均按照模型框架、变量口径、验证方案和后续替换口径进行表述": "报告均按照模型框架、变量口径、验证方案和数据补充接口进行表述",
            "4.10 模型输出、应用接口与真实数据替换口径": "4.10 模型输出与应用接口",
        },
    )


def ensure_static_toc(doc):
    toc = find_paragraph(doc, "目录")
    first_chapter = find_paragraph(doc, "1 概述")
    has_entries = False
    seen_toc = False
    for para in doc.paragraphs:
        if para._element is toc._element:
            seen_toc = True
            continue
        if para._element is first_chapter._element:
            break
        if seen_toc and para.text.strip():
            has_entries = True
            break
    if has_entries:
        return
    entries = [
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
    for entry in entries:
        paragraph_before(first_chapter._element, first_chapter._parent, entry, first_indent=False)


def integrate_tables(doc):
    # Table 1: phase-to-output table at the end of Chapter 1.
    t1 = find_table(doc, "阶段")
    add_table_bridge(
        t1,
        "为了使技术路线与项目实施过程对应起来，表1将课题一已经形成的阶段性工作、时间范围和主要成果进行归纳。该表不是孤立的进度清单，而是后文各研究模块的来源说明：影响因素分析、机理模型、特征库和验证方案均来自这些阶段成果的逐步沉淀。",
        "表1  课题一阶段性工作与报告内容衔接",
        "由表1可以看出，报告正文的第2章至第7章并非并列堆砌，而是沿着“调研与方案制定—影响因素和机理模型—特征库与验证方案—技术报告集成”的路径展开。后续章节将在该基础上分别展开资源行为、能力建模、智能分类和数据验证的具体技术内容。",
    )

    # Table 2: resource characteristics should sit before the chapter summary.
    t2 = find_table(doc, "资源类型")
    summary2 = find_paragraph(doc, "2.8 本章小结")
    move_table_before(t2, summary2)
    add_table_bridge(
        t2,
        "在上述影响因素体系中，不同资源的作用机理并不相同。为避免只停留在概念描述，表2将典型资源的主要调节方式、关键状态变量和主要限制条件进行汇总，用于说明为什么后续建模必须采用分资源、分场景的特征表达。",
        "表2  典型资源调节特性与约束差异",
        "表2表明，光伏、储能、充电站、工业负荷和楼宇空调虽然都可以纳入虚拟电厂，但其可调能力来源和限制因素完全不同。正是这种差异，决定了第三章需要区分调节意愿与动态能力，第四章需要建立分资源能力模型，第五章需要面向市场需求进行智能分级分类。",
    )

    # Table 3: data theme table belongs to Section 6.3.
    t3 = find_table(doc, "主题表")
    target6 = find_paragraph(doc, "6.4 特征计算与样本组织")
    move_table_before(t3, target6)
    add_table_bridge(
        t3,
        "围绕上述数据架构，特征库需要通过若干主题表承载模型所需的信息。表3列出各主题表的核心字段和主要用途，可作为后续数据接口设计、特征计算任务和模型输入输出对齐的基础。",
        "表3  多维行为特征库核心主题表",
        "从表3可以看出，资源主数据和运行状态表解决“资源是什么、当前处于什么状态”的问题，市场信号和调节事件表解决“面对什么任务”的问题，调节结果和行为特征表则负责记录“实际响应如何、后续模型如何更新”。这些表共同构成第2章至第5章模型落地的数据闭环。",
    )

    # Table 4: validation metrics table belongs to Section 7.3.
    t4 = find_table(doc, "评价对象")
    target7 = find_paragraph(doc, "7.4 验证流程与基准模型")
    move_table_before(t4, target7)
    add_table_bridge(
        t4,
        "为了避免将“90%精度”理解为单一、模糊的总指标，本报告将模型评价拆解到不同输出对象。表4给出各类评价对象、候选指标和90%目标的可能含义，后续可根据项目验收口径选择最终指标。",
        "表4  模型精度评价对象与候选指标",
        "表4的作用是把项目精度要求落到可计算指标上：容量预测关注连续值误差，可调用判断和等级分类关注分类一致性，响应曲线关注时延和跟踪误差，资源池构建关注市场执行效果。通过这种拆解，第7章的验证方案能够与第4章能力模型和第5章分类模型直接衔接。",
    )


def main():
    doc = Document(SOURCE)
    remove_repeated_data_placeholders(doc)
    ensure_static_toc(doc)
    integrate_tables(doc)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
