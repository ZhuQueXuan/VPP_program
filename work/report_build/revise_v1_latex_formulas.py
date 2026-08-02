from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt


SOURCE = Path("outputs/reports/技术报告-课题一v1-表文衔接修正版.docx")
OUTPUT = Path("outputs/reports/技术报告-课题一v1-公式LaTeX修正版.docx")


REPLACEMENTS = [
    (
        "调节意愿模型可采用分层离散选择或广义线性混合模型进行表达。",
        [
            ("text", "调节意愿模型可采用分层离散选择或广义线性混合模型进行表达。对于资源i在时刻t、市场场景m下的参与概率，可用 \\(W_{\\mathrm{part},i}(t,m)\\) 表示；对于愿意开放的容量比例，可用 \\(W_{\\mathrm{open},i}(t,m)\\) 表示；对于任务期间保持参与的概率，可用 \\(W_{\\mathrm{keep},i}(t,m)\\) 表示。概念上，调节意愿可表示为："),
            ("formula", "\\[ W_i(t,m)=F\\left(B_i(t,m)-K_i(t,m),\\ Risk_i(t,m),\\ Task_m,\\ Pref_i,\\ State_i(t),\\ H_i(t)\\right) \\]"),
            ("text", "其中，\\(B\\) 表示预计收益，\\(K\\) 表示机会成本和不便成本，\\(Risk\\) 表示风险感知，\\(Task\\) 表示调节任务属性，\\(Pref\\) 表示用户偏好，\\(State\\) 表示当前业务或用能状态，\\(H\\) 表示历史参与反馈。"),
        ],
    ),
    (
        "从工程实现看，能力向量可以表示为",
        [
            ("text", "从工程实现看，动态能力不宜简化为单一功率值，而应以能力向量形式表达。能力向量可表示为："),
            ("formula", "\\[ C_i(t)=\\left[P_{\\mathrm{up},i}(t),\\ P_{\\mathrm{down},i}(t),\\ E_i(t),\\ T_i(t),\\ R_i(t),\\ Acc_i(t),\\ Rec_i(t),\\ Prob_i(t)\\right] \\]"),
            ("text", "其中，\\(P_{\\mathrm{up}}\\) 和 \\(P_{\\mathrm{down}}\\) 表示上下调功率边界，\\(E\\) 表示可调电量，\\(T\\) 表示可持续时间，\\(R\\) 表示爬坡或响应速度，\\(Acc\\) 表示调节精度，\\(Rec\\) 表示恢复时间或反弹风险，\\(Prob\\) 表示在当前状态和不确定性条件下的可用概率。该表达既保留了资源物理含义，也便于后续与市场场景进行匹配。"),
        ],
    ),
    (
        "本研究建议将资源i在时刻t、市场场景m下的可信可调用能力表示为",
        [
            ("text", "本研究建议将资源i在时刻t、市场场景m下的可信可调用能力写成由客观能力、意愿开放、场景匹配、历史可靠度和安全校核共同修正的形式："),
            ("formula", "\\[ A_i(t,m)=C_i(t)\\times W_{\\mathrm{open},i}(t,m)\\times Q_{\\mathrm{match},i}(t,m)\\times R_{\\mathrm{history},i}(t)\\times S_{\\mathrm{safe},i}(t) \\]"),
            ("text", "其中，\\(C_i(t)\\) 为动态能力向量，\\(W_{\\mathrm{open}}\\) 表示意愿开放比例，\\(Q_{\\mathrm{match}}\\) 表示资源能力与市场任务要求的匹配程度，\\(R_{\\mathrm{history}}\\) 表示历史可靠度修正，\\(S_{\\mathrm{safe}}\\) 表示设备、电网和业务安全校核结果。该表达不是最终固定算法，而是阶段性机理模型，用于明确变量关系、数据需求和后续建模方向。"),
        ],
    ),
    (
        "可调容量建模首先必须明确基线。",
        [
            ("text", "可调容量建模首先必须明确基线。对于负荷型资源，基线 \\(P_{\\mathrm{base}}(t)\\) 表示未参与调节时的预计用电功率；实际响应量通常由基线功率与实际功率之差得到。对于发电型或储能型资源，基线既可能表示计划出力，也可能表示市场申报曲线或调度前预测曲线。若基线不准确，可调容量和响应效果都会被系统性高估或低估。需求响应文献中也指出，基线方法既关系到补偿结算，也关系到响应效果评价，甚至可能引发基线操纵问题[14]。因此，本课题应把基线预测作为可调容量建模的前置环节。"),
        ],
    ),
    (
        "在统一符号上，可将资源i在时刻t、预测窗口H内的向上可调功率记为",
        [
            ("text", "在统一符号上，可将资源i在时刻t、预测窗口H内的向上可调功率、向下可调功率和可调电量分别表示为："),
            ("formula", "\\[ P_{\\mathrm{up},i}(t,H),\\quad P_{\\mathrm{down},i}(t,H),\\quad E_i(t,H) \\]"),
            ("text", "其中，“向上”和“向下”应在项目中统一正负方向：可以按虚拟电厂对外等效出力增加/减少定义，也可以按用户侧负荷增加/减少定义，但正式建模前必须固化口径。响应能力可表示为："),
            ("formula", "\\[ R_i(t,H)=\\left[\\tau_i,\\ \\mathrm{ramp}_i,\\ \\mathrm{dur}_i,\\ \\mathrm{acc}_i,\\ \\mathrm{rec}_i,\\ \\mathrm{prob}_i\\right] \\]"),
            ("text", "上述分量分别对应响应时延、爬坡速率、可持续时长、跟踪精度、恢复时间和可用概率。"),
        ],
    ),
    (
        "主观意愿修正来自第三章的W_open",
        [
            ("text", "可调容量和响应能力最终需要从“理论可用”转化为“可信可调用”。因此，本章在特征建模中引入主观意愿修正、历史可靠度修正、通信控制可达性修正和安全校核修正。主观意愿修正来自第三章的 \\(W_{\\mathrm{open}}\\)，用于表示用户愿意开放的能力比例；历史可靠度修正来自过去调节事件的完成率、响应偏差、退出频次和考核结果；通信控制可达性修正用于处理设备离线、数据延迟、控制失败等问题；安全校核修正用于剔除可能突破设备、电网、生产或舒适边界的能力。"),
        ],
    ),
    (
        "综合特征可表示为",
        [
            ("text", "综合特征可表示为客观能力、意愿、场景匹配、可靠度和安全校核共同作用的融合函数："),
            ("formula", "\\[ A_i(t,m,H)=\\Phi\\left(C_i(t,H),\\ W_i(t,m),\\ Q_i(t,m),\\ R_i(t),\\ S_i(t)\\right) \\]"),
            ("text", "其中，\\(C\\) 表示客观能力向量，\\(W\\) 表示意愿开放程度，\\(Q\\) 表示市场场景匹配程度，\\(R\\) 表示历史可靠度，\\(S\\) 表示安全校核结果，\\(\\Phi\\) 表示融合函数。第一阶段可采用规则加权和分段折减的可解释方法，便于向评审说明模型逻辑；数据积累后，可引入广义加性模型、梯度提升树、随机森林、图模型或时序深度学习模型进行非线性修正，但仍应保留物理约束和安全边界作为硬约束。"),
        ],
    ),
    (
        "因此，本研究建议将每类市场任务抽象为需求向量",
        [
            ("text", "因此，本研究建议将每类市场任务抽象为需求向量："),
            ("formula", "\\[ M_m=\\left[P_{\\mathrm{req}},\\ E_{\\mathrm{req}},\\ T_{\\mathrm{req}},\\ \\tau_{\\mathrm{req}},\\ \\mathrm{ramp}_{\\mathrm{req}},\\ \\mathrm{acc}_{\\mathrm{req}},\\ \\mathrm{rel}_{\\mathrm{req}},\\ \\mathrm{cost}_{\\mathrm{req}},\\ \\mathrm{green}_{\\mathrm{req}}\\right] \\]"),
            ("text", "其中，\\(P_{\\mathrm{req}}\\) 表示功率规模要求，\\(E_{\\mathrm{req}}\\) 表示能量要求，\\(T_{\\mathrm{req}}\\) 表示持续时间要求，\\(\\tau_{\\mathrm{req}}\\) 表示响应时延要求，\\(\\mathrm{ramp}_{\\mathrm{req}}\\) 表示爬坡要求，\\(\\mathrm{acc}_{\\mathrm{req}}\\) 表示调节精度要求，\\(\\mathrm{rel}_{\\mathrm{req}}\\) 表示可靠度要求，\\(\\mathrm{cost}_{\\mathrm{req}}\\) 表示成本约束，\\(\\mathrm{green}_{\\mathrm{req}}\\) 表示绿色属性或消纳协同要求。不同市场的权重不同，不能用统一权重评价所有资源。"),
        ],
    ),
    (
        "资源分类的直接应用是构建面向不同市场的候选资源池。",
        [
            ("text", "资源分类的直接应用是构建面向不同市场的候选资源池。对于市场m，可将资源i的市场适配度表示为："),
            ("formula", "\\[ S_{i,m}=\\mathrm{Match}\\left(F_i,M_m\\right)\\times R_i\\times W_i\\times Safe_i \\]"),
            ("text", "其中，\\(F_i\\) 为资源能力特征向量，\\(M_m\\) 为市场需求向量，\\(R_i\\) 为历史可靠度，\\(W_i\\) 为意愿开放程度，\\(Safe_i\\) 为安全校核结果。\\(\\mathrm{Match}\\) 函数可根据不同市场设置权重，也可通过历史执行结果学习得到。"),
        ],
    ),
]


def set_run_font(run, font_name="宋体", size_pt=12):
    run.font.name = font_name
    run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), font_name)
    run.font.size = Pt(size_pt)


def style_text_paragraph(paragraph):
    paragraph.style = "Normal"
    paragraph.paragraph_format.first_line_indent = Pt(24)
    paragraph.paragraph_format.space_after = Pt(6)
    paragraph.paragraph_format.line_spacing = 1.25
    for run in paragraph.runs:
        set_run_font(run, "宋体", 12)


def style_formula_paragraph(paragraph):
    paragraph.style = "Normal"
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.first_line_indent = Pt(0)
    paragraph.paragraph_format.space_before = Pt(3)
    paragraph.paragraph_format.space_after = Pt(6)
    for run in paragraph.runs:
        set_run_font(run, "Cambria Math", 11)


def insert_before(paragraph, kind, text):
    new_para = paragraph.insert_paragraph_before(text)
    if kind == "formula":
        style_formula_paragraph(new_para)
    else:
        style_text_paragraph(new_para)
    return new_para


def delete_paragraph(paragraph):
    element = paragraph._element
    element.getparent().remove(element)
    paragraph._p = paragraph._element = None


def main():
    doc = Document(SOURCE)
    replaced = 0
    for trigger, items in REPLACEMENTS:
        for paragraph in list(doc.paragraphs):
            if paragraph.text.strip().startswith(trigger) or trigger in paragraph.text:
                for kind, text in items:
                    insert_before(paragraph, kind, text)
                delete_paragraph(paragraph)
                replaced += 1
                break
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    print(OUTPUT)
    print(f"replaced={replaced}")


if __name__ == "__main__":
    main()
