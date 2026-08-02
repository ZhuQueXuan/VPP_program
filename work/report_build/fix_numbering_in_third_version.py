from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt


ROOT = Path(__file__).resolve().parents[2]
DOCX = ROOT / "outputs" / "reports" / "技术报告-课题一-虚拟电厂多元异质资源调节行为分析与智能分类方法-第三版.docx"
FALLBACK = ROOT / "outputs" / "reports" / "技术报告-课题一-虚拟电厂多元异质资源调节行为分析与智能分类方法-第三版-序号修正版.docx"


NUMBERED_GROUPS = {
    "toc": [
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
    ],
    "factor_steps": [
        "建立资源类型、市场场景和调节任务的统一编码。",
        "将价格、补偿、考核、SOC、在线车辆数、温度、持续时间等因素转化为可观测变量。",
        "分别识别变量对调节意愿、动态能力和实际响应结果的作用对象。",
        "在真实样本中开展统计检验、模型拟合、因果解耦和典型事件回放。",
    ],
    "integrated_model": [
        "主体侧建模：用户价格敏感度、用能偏好、绿色价值取向、风险偏好和授权方式。",
        "客体侧建模：资源物理属性、实时状态、响应速度、持续时间、恢复间隔和安全边界。",
        "聚合侧建模：资源组合约束、控制策略、通信链路、聚合商调度目标和市场任务要求。",
        "输出侧建模：协同可调容量、综合响应能力、可靠度、市场适配度和限制因素解释。",
    ],
    "classification_steps": [
        "构建资源能力指标宽表，形成分资源、分事件、分市场场景的样本。",
        "通过规则基准或专家标定形成基础等级，用于解释和初始校验。",
        "使用自监督表征学习提取资源时序行为特征，减少对人工标签依赖。",
        "通过聚类区分度、等级稳定性和人工/规则基准一致性验证分类可靠性。",
        "在典型市场场景中回放分类结果，评估资源配置效率和响应执行效果提升。",
    ],
    "dataset_split": [
        "训练集：用于模型参数估计和特征选择。",
        "验证集：用于阈值、超参数和特征组合调优。",
        "测试集：用于最终精度评价，不参与模型训练。",
        "跨场景验证集：用于检验跨资源类型、跨市场场景和跨时间尺度的泛化能力。",
    ],
}

BULLETS = {
    "完整性：核心资源档案字段不得为空，调节事件必须具备指令、基线、实际功率和结果记录。",
    "准确性：功率、能量、价格、SOC、温度等字段统一单位并检查物理范围。",
    "时序一致性：市场、气象、状态、指令和结果数据统一时区，记录采样误差。",
    "逻辑一致性：不支持V2G的充电桩不得出现放电状态，光伏夜间无配储时不得记录正向发电能力。",
    "异常处理：原始数据不直接覆盖，保留异常标识；调节事件关键区间原则上不进行无依据填补。",
    "完善真实数据接入：优先获取日前/实时价格、系统负荷、资源运行状态、调节事件、响应曲线、用户授权和结算数据。",
    "完成模型实证验证：明确90%精度评价口径，形成分资源、分场景、分时间尺度的验证结果。",
    "加强因果与时序研究：识别价格、天气、SOC、授权和业务状态对资源行为的直接效应、交互效应和滞后效应。",
    "推进智能分类应用：将资源能力等级、市场适配分类和约束校核结果接入虚拟电厂运营服务模块。",
    "形成可复用成果：沉淀数据字典、特征工程规范、模型验证规范和面向多市场运营的资源评价方法。",
}


def set_font(run):
    run.font.name = "宋体"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    run._element.rPr.rFonts.set(qn("w:ascii"), "宋体")
    run._element.rPr.rFonts.set(qn("w:hAnsi"), "宋体")
    run.font.size = Pt(11)


def clear_runs(paragraph):
    for run in list(paragraph.runs):
        paragraph._p.remove(run._r)


def set_plain_text(paragraph, text, indent=False):
    paragraph.style = paragraph.part.document.styles["Normal"]
    paragraph.paragraph_format.left_indent = Pt(18) if indent else None
    paragraph.paragraph_format.first_line_indent = None
    paragraph.paragraph_format.space_after = Pt(4)
    paragraph.paragraph_format.line_spacing = 1.10
    clear_runs(paragraph)
    run = paragraph.add_run(text)
    set_font(run)


def main():
    doc = Document(DOCX)

    number_map = {}
    for items in NUMBERED_GROUPS.values():
        for idx, text in enumerate(items, 1):
            number_map[text] = f"{idx}. {text}"

    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if text in number_map:
            set_plain_text(paragraph, number_map[text], indent=True)
        elif text in BULLETS:
            set_plain_text(paragraph, f"• {text}", indent=True)

    try:
        doc.save(DOCX)
        print(DOCX)
    except PermissionError:
        doc.save(FALLBACK)
        print(FALLBACK)


if __name__ == "__main__":
    main()
