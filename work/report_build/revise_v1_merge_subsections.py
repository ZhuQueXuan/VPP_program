from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt


SOURCE = Path("outputs/reports/技术报告-课题一v1-Word公式对象修正版.docx")
OUTPUT = Path("outputs/reports/技术报告-课题一v1-二级标题整合修正版.docx")


RENAME_HEADINGS = {
    "2.3 市场环境对资源行为的驱动机制": "2.3 市场环境与外部状态耦合影响",
    "2.5 用户行为偏好与聚合控制因素": "2.4 用户行为偏好与聚合控制因素",
    "2.6 影响因素可观测变量与特征化表达": "2.5 可观测变量与分析方法",
    "2.8 本章小结": "2.6 本章小结",
    "3.1 研究任务与问题界定": "3.1 研究任务与总体模型框架",
    "3.2 调节意愿的潜变量结构": "3.2 调节意愿结构与模型表达",
    "3.4 动态调节能力的能力向量结构": "3.3 动态调节能力结构与典型资源机理",
    "3.6 意愿与能力耦合机理": "3.4 意愿能力耦合与可信可调用能力",
    "3.7 实际响应与闭环反馈机制": "3.5 实际响应、反馈机制与模型验证",
    "3.9 本章小结": "3.6 本章小结",
    "4.2 基线、可调容量与响应能力定义": "4.2 基线定义、容量边界与数据特征工程",
    "4.4 分资源可调容量建模方法": "4.3 分资源可调容量与响应能力建模",
    "4.6 主观意愿与客观能力一体化特征": "4.4 主客观约束融合与聚合层能力建模",
    "4.8 模型训练、校准与不确定性估计": "4.5 模型训练、精度评价与应用接口",
    "4.11 本章小结": "4.6 本章小结",
    "5.2 多元市场调节需求画像": "5.2 市场需求画像与资源能力特征体系",
    "5.4 分级规则与等级体系设计": "5.3 分级规则与智能分类模型",
    "5.6 市场适配度计算与资源池构建": "5.4 市场适配、资源池构建与约束校核",
    "5.8 分类效果验证与评价指标": "5.5 分类效果验证与评价指标",
    "5.9 本章小结": "5.6 本章小结",
}


DELETE_HEADINGS = {
    "2.4 外部环境与资源状态的耦合影响",
    "2.7 分析方法与技术实现路径",
    "3.3 调节意愿模型表达",
    "3.5 典型资源动态能力形成机理",
    "3.8 模型验证与精度评价衔接",
    "4.3 数据基础与特征工程框架",
    "4.5 响应能力特征建模方法",
    "4.7 聚合层能力建模与网络约束",
    "4.9 精度评价与90%指标落地",
    "4.10 模型输出与应用接口",
    "5.3 资源能力画像与分类特征体系",
    "5.5 智能分类模型方法",
    "5.7 约束校核与分类结果修正",
}


TEXT_REPLACEMENTS = {
    "第2章重点研究多元异质资源行为影响因素，第3章研究调节意愿与动态调节能力影响机理，第4章研究可调容量与响应能力特征建模方法，第5章研究面向多元市场需求的资源智能分级分类方法。": "第2章重点研究多元异质资源行为影响因素，第3章研究调节意愿与动态调节能力影响机理，第4章研究可调容量与响应能力特征建模方法，第5章研究面向多元市场需求的资源智能分级分类方法。",
}


def set_heading_text(paragraph, text):
    paragraph.clear()
    run = paragraph.add_run(text)
    run.font.name = "黑体"
    run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "黑体")


def delete_paragraph(paragraph):
    element = paragraph._element
    element.getparent().remove(element)
    paragraph._p = paragraph._element = None


def insert_paragraph_before(paragraph, text):
    new_para = paragraph.insert_paragraph_before(text)
    new_para.style = "Normal"
    new_para.paragraph_format.first_line_indent = Pt(0)
    new_para.paragraph_format.space_after = Pt(3)
    if new_para.runs:
        run = new_para.runs[0]
        run.font.name = "宋体"
        run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "宋体")
        run.font.size = Pt(12)


def ensure_static_toc(doc):
    toc = None
    first_chapter = None
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        style = paragraph.style.name if paragraph.style else ""
        if style == "Heading 1" and text == "目录":
            toc = paragraph
        elif style == "Heading 1" and text.startswith("1 概述"):
            first_chapter = paragraph
            break
    if toc is None or first_chapter is None:
        return
    has_entries = False
    seen_toc = False
    for paragraph in doc.paragraphs:
        if paragraph._element is toc._element:
            seen_toc = True
            continue
        if paragraph._element is first_chapter._element:
            break
        if seen_toc and paragraph.text.strip():
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
        insert_paragraph_before(first_chapter, entry)


def main():
    doc = Document(SOURCE)
    deleted = 0
    renamed = 0

    for paragraph in list(doc.paragraphs):
        text = paragraph.text.strip()
        style = paragraph.style.name if paragraph.style else ""
        if style == "Heading 2" and text in DELETE_HEADINGS:
            delete_paragraph(paragraph)
            deleted += 1
            continue
        if style == "Heading 2" and text in RENAME_HEADINGS:
            set_heading_text(paragraph, RENAME_HEADINGS[text])
            renamed += 1
            continue
        if text:
            new_text = paragraph.text
            for old, new in TEXT_REPLACEMENTS.items():
                new_text = new_text.replace(old, new)
            if new_text != paragraph.text:
                paragraph.clear()
                run = paragraph.add_run(new_text)
                run.font.name = "宋体"
                run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "宋体")
                if paragraph.style.name == "Normal":
                    paragraph.paragraph_format.first_line_indent = Pt(24)
                    paragraph.paragraph_format.space_after = Pt(6)
                    paragraph.paragraph_format.line_spacing = 1.25

    ensure_static_toc(doc)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    print(OUTPUT)
    print(f"renamed={renamed}, deleted={deleted}")


if __name__ == "__main__":
    main()
