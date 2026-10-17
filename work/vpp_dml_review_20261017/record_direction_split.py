from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
NOTE='work/process_notes/2026-10-17_DML代码功能与资源调研衔接说明.md'
CANDIDATE='work/process_notes/2026-10-17_同事DML资源清单与下一轮资源候选.md'
CHAT='01a148a5-8e11-73d2-9b7b-766723014a3f'

def replace(path,old,new):
    p=ROOT/path;t=p.read_text(encoding='utf-8-sig')
    assert t.count(old)==1,(path,old,t.count(old))
    p.write_text(t.replace(old,new,1),encoding='utf-8')
def after_title(path,block):
    p=ROOT/path;t=p.read_text(encoding='utf-8-sig');a,b=t.split('\n',1)
    p.write_text(a+'\n\n'+block+'\n'+b,encoding='utf-8')
def main():
    brief='用户指定分两个方向：新建项目对话列同事40个模拟个体及代表性资源候选，先推荐、待用户选择后再深调研；原对话解释代码功能及资源调研衔接。40是四类个体（工业12/空调12/EV8/储能8），非40种设备；工业无具体子类。新对话首轮清单及4项推荐已完成，未选对象或启动新实验。'
    p=ROOT/'docs/DECISION_LOG.md';t=p.read_text(encoding='utf-8-sig');assert '## D070｜' not in t
    t+=f'''\n\n## D070｜资源候选与DML代码解释分两个对话推进

- 日期：2026-10-17；依据用户明确要求。{brief}
- 已按当前VPP_program本地项目创建新对话`{CHAT}`，输入完整中文Prompt；要求核验id/类型、有限官方网页核查、区分物理和激励数据，待用户选择再深入。新对话已有40行个体清单与4项建议；推荐不是选型决定或数据准入，独立具名过程记录，不同步写相同共享台账。
- 原对话已完成模块、输入、五激励特征、两阶段、敏感性/参考基线/离散度/AGC及六类追加证据说明。建议保留曲线/公式/参数/约束研究，进一步区分物理能力、指令执行、经济激励、选择授权四层；按可观察问题裁剪代码，不为填问卷/绿色/未来字段补造数据。原代码亦需补时点/时钟、阻断、完整留出和新样本推理，不能将程序缺口全推给调研。
- 后续每个用户选定对象可增加“各层证据—可支持输出—缺口”清单；这是本轮分析建议，不等于已批准DML替换方案、全部六类升级或深度研究开工。现用两份核心框架和103不改，D068/D069科学结果、负控失败、六类限定成果及P1/103未过保持。
- 本次无新实验、无新实际数据准入；DATA_CARD/EXPERIMENT_LOG不为说明刷新。原数据/代码/参数不变，不自动整合、自监督、多智能体或GPU。说明见[代码与调研衔接](../{NOTE})，第一方向见[清单与候选](../{CANDIDATE})、[启动Prompt](../work/vpp_dml_review_20261017/resource_research_thread_prompt_20261017.md)。\n'''
    p.write_text(t,encoding='utf-8')
    for path,heading in [('outputs/ROADMAP_v2.md','## 2. 对v1的审查'),('outputs/第一阶段两周执行计划_v2_20261013.md','## 1. 本期单一研究样板与范围')]:
        replace(path,'最新补记（D069，2026-10-17）：','前序补记（D069，2026-10-17）：')
        replace(path,heading,heading+f'\n\n最新补记（D070，2026-10-17）：{brief}原对话代码/调研衔接说明已完成，原六类和D068/D069结果保持；P1/103未过，不因解释或推荐升级。见[衔接说明](../{NOTE})、[资源清单与候选](../{CANDIDATE})。')
        replace(path,'当前D069：用户授权的既有模拟任务适配已实际完成；',
            f'当前D070：按用户要求分流，资源清单/推荐在新对话完成并等待用户选型，原对话代码与调研衔接解释完成；未开始新深调研/实验。见[说明](../{NOTE})。\n\n前序D069：用户授权的既有模拟任务适配已实际完成；')
    replace('AGENTS.md','| 1 | [docs/DECISION_LOG.md](docs/DECISION_LOG.md) | 先读D069',
            '| 1 | [docs/DECISION_LOG.md](docs/DECISION_LOG.md) | 先读D070两方向/新对话资源推荐待选与代码调研衔接，再读D069')
    replace('AGENTS.md','- 2026-10-17现用D069：',f'- 2026-10-17现用D070：{brief}原对话模块解释及六类追加证据建议已完成，后续按物理/指令/激励/选择授权区分输出，代码按可核问题适配。说明{NOTE}；第一方向{CANDIDATE}，对话{CHAT}。无新数据准入/实验，D069负控失败及原六类/P1未过保持，不自动整合/高级分支。\n- 2026-10-17前序D069：')
    after_title('项目文件索引.md',f'- 2026-10-17 D070：[DML功能与资源调研衔接]({NOTE})、[40个体清单与候选]({CANDIDATE})、[新对话启动Prompt](work/vpp_dml_review_20261017/resource_research_thread_prompt_20261017.md)。用户指定分流：候选待用户选型，本对话解释完成，无新实验或阶段升级。\n')
    p=ROOT/'work/vpp_dml_review_20261017/README.md';t=p.read_text(encoding='utf-8')
    t+=f'\n## 两方向接续（D070）\n\n[代码功能与调研衔接](../process_notes/2026-10-17_DML代码功能与资源调研衔接说明.md)已完成；另建用户对话负责[40个体与候选](../process_notes/2026-10-17_同事DML资源清单与下一轮资源候选.md)，待用户选择再深调研。原实验结果和现用框架不变。\n'
    p.write_text(t,encoding='utf-8');print('D070 recorded; no data or experiment status changed.')

if __name__=='__main__':main()
