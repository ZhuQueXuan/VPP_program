from pathlib import Path
import hashlib
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
NOTE='work/process_notes/2026-10-17_已有模拟数据接入DML.md'
ENTRY='work/vpp_dml_project_trial_20261017/README.md'

def replace(path,old,new):
    p=ROOT/path;t=p.read_text(encoding='utf-8-sig')
    if t.count(old)!=1:raise ValueError((path,old,t.count(old)))
    p.write_text(t.replace(old,new,1),encoding='utf-8')
def after_title(path,block):
    p=ROOT/path;t=p.read_text(encoding='utf-8-sig');first,rest=t.split('\n',1)
    p.write_text(first+'\n\n'+block+'\n'+rest,encoding='utf-8')
def main():
    verification=json.loads((HERE/'verification.json').read_text(encoding='utf-8'))
    assert verification['status']=='passed'
    ph=hashlib.sha256((HERE/'protocol.json').read_bytes()).hexdigest()
    brief='用户明确授权用已有模拟数据接入同事DML；解耦2.4主实验3456独立任务，沿原聚合体1728训练/576验证/1152测试，训练内部3折。任务级0.8/1.2/1.6相对0.4元/kWh的完成率增量适配已实跑/复跑，无伪造小时历史或绿色/调查。高档测试真值11.1702pp，DML线性/森林估12.3038/12.3131pp；16类均值绝对偏差OLS4.5823、线性DML5.2123、森林7.4083pp，森林对预设零效应PV/储能估9.7682/15.5005pp，未形成稳定优势。'
    links=f'[接入结果](../{NOTE})、[运行入口](../{ENTRY})'
    p=ROOT/'docs/DECISION_LOG.md';t=p.read_text(encoding='utf-8-sig')
    assert '## D069｜' not in t
    t+=f'''\n\n## D069｜现有模拟任务接入同事DML核心与固定对照试验

- 日期：2026-10-17。用户进一步明确要求使用我们已有模拟数据尝试；本条在D068外来包检查基础上增加该具体适配授权，未授权资源组合、市场适配、自监督、多智能体或正式阶段升级。
- {brief}
- 任务级协议SHA256 `{ph}`，卡DC-20261017-02；类型及8项事前数值/授权，三处理虚拟变量，全部未授权/拒绝/物理失败保留。交叉拟合、LightGBM及两类最终阶段复用原核心；另设TaskDML覆盖分组/面板协议并在最终拟合前阻断失败诊断，未修改原同事文件。潜在真值只在预测保存后由评价读取，未使用latent/接受概率/参与结果输入。
- 两次固定配置完成，25920留出估计复跑差≤1.02e-15；独立原表3456对应真值、3690指标数值及5184线性DML SVD估计核验通过。训练3聚合体、测试2聚合体，不报稳健显著区间；验证1/测试36域外行保留，无调参/剪裁或硬置零。
- 这证明DML核心可复用但当前配置的类型差异/零效应检验不足；OLS亦有假效应，不将任何模型认作已通过因果解耦。低档森林相对几项参照较好，中/高档未稳定超过OLS，所有预设方法/档位均保留。个体潜在效果含未见阈值/保留成本，不以个体误差全归估计器。
- 原模拟内部2.4、六类实测成果及D068结果保持；模拟试验不代表真实激励弹性、意愿、容量、全课题精度或P1/103通过。此轮接入完成，后续改进须训练/验证定方案并另留独立检验，不能在已见测试补分。无GPU/服务器/上传/提交。见{links}。\n'''
    p.write_text(t,encoding='utf-8')
    replace('docs/DATA_CARD.md','卡版本：DC-20261017-01｜建立日期：2026年10月13日；更新日期：2026年10月17日',
            '卡版本：DC-20261017-02｜建立日期：2026年10月13日；更新日期：2026年10月17日')
    replace('docs/DATA_CARD.md','## 同事DML交付：仅全合成方法核验（D068）',f'''## 既有解耦模拟2.4：同事DML任务级适配限定准入（D069）

- 用户明确要求使用已有模拟数据。来源data/驱动因素解耦模拟数据集_v2内部2.4；原件不重生成，读取01事前输入、02观察完成比例、01实体，03四价潜在结果仅评价。3456/96实体/16类；每实体36全因子，四价各9；全部观察对应潜在真值差0。
- 研究对象：既有状态、授权和历史固定，补贴从0.4变为0.8/1.2/1.6元/kWh对请求方向完成率的即时增量。不是统一网侧MW/连续小时或真实容量；不补造问卷/绿色/AGC/参考价。只选类型、额定功率、难度、时长、事前状态/接受历史、温度、生产和事前授权；处理后参与/开放/执行及潜在成本/概率不输入。
- 原train聚合体01—03/1728任务/48实体，validation04/576/16，test05—06/1152/32；train内部聚合体3折，编码/缩放不读留出结果。原数据非连续状态，跳过build_dataset与伪小时，continuous四天也不拼作七天历史。0.25仅边际排列概率，不强称序贯已知倾向。
- 协议SHA256 `{ph}`，全部未授权/拒绝/失败保留，无剪裁或真值类型硬置零。潜在结果是固定不可见阈值/个体成本的实现值；CATE不保证恢复逐任务实现差，主报整体/类型均值，个体MAE/RMSE另报。PV/储能仅本模拟预设负控。
- 代码/文件SHA与训练隔离见运行收据，验证1/测试36输入超训练逐列范围保留。2次25920估计容差一致、独立原表/3690指标/5184SVD通过；不是独立物理源或新实测准入。原卡DC-20261017-01及六类冻结卡保留。见{links}。

## 同事DML交付：仅全合成方法核验（D068；原卡DC-20261017-01）''')
    after_title('docs/EXPERIMENT_LOG.md',f'''## BL-DML-PROJECT-TASK-20261017｜既有模拟任务接入与留出比较（D069）

- {brief}
- 拟合前协议`{ph}`/卡DC-20261017-02，工作目录work/vpp_dml_project_trial_20261017。RUN01/02均completed，约3.99/2.48秒；复用原核心，替换独立任务数据协议、分组与评价。原数据/核心/五模型/三价参数不根据留出成绩调整。
- 三聚合体crossfit；LightGBM300树，森林200树/叶40/采样0.3，series ridge1e-4；参照零、训练常数差、同特征OLS。任务完成率为结果，不用接受/开放/执行和真值作特征；先保存留出预测再读03评价。第一阶段识别筛查通过，cond4.021，不据此认因果识别成立。
- 25920预测/615组结果/30摘要保留；复跑预测最大差1.02e-15、组指标9.95e-14，非逐字节相同；原表3456真值对应、3690指标与5184线性预测独立SVD核验通过。测试高档负控144条，线性DML81.94%/森林100%超过预定5pp绝对值阈值，是描述率非显著性。验证1/测试36域外，未删除/路由。
- 16类高档均值图全点导出PNG/SVG，PNG目检，SVG未另渲染。单体实现效应含隐变量噪声，主报类型/总体；测试仅2聚合体不报CI。接入闭环完成，零效应/相对优势不足保持失败，未替换现用模型或称P1/103通过，无GPU/上传。见{links}。
''')
    for path,heading in [('outputs/ROADMAP_v2.md','## 2. 对v1的审查'),('outputs/第一阶段两周执行计划_v2_20261013.md','## 1. 本期单一研究样板与范围')]:
        replace(path,'最新补记（D068，2026-10-17）：','前序补记（D068，2026-10-17）：')
        replace(path,heading,heading+f'\n\n最新补记（D069，2026-10-17）：{brief}接入实跑及独立核验完成，效果不足保留；原六类和P1状态保持，不进入整合/高级分支。见{links}。')
        replace(path,'当前D068：同事DML交付只作候选审查/全合成实跑，',
                f'当前D069：用户授权的既有模拟任务适配已实际完成；当前配置类型差异/负控检验不足，不替换模型、不升级P1。见[结果](../{NOTE})。\n\n前序D068：同事DML交付只作候选审查/全合成实跑，')
    replace('AGENTS.md','| 1 | [docs/DECISION_LOG.md](docs/DECISION_LOG.md) | 先读D068',
            '| 1 | [docs/DECISION_LOG.md](docs/DECISION_LOG.md) | 先读D069既有模拟任务DML适配/类型差异与零效应失败，再读D068')
    replace('AGENTS.md','- 2026-10-17现用D068：',f'- 2026-10-17现用D069：{brief}卡DC-20261017-02；25920预测两次容差一致，独立3690指标/5184SVD通过，测试36域外保留；只任务完成率/模拟用途，P1/103未过，原核心/模拟源/六类成果保持，不整合/高级分支。入口{ENTRY}及{NOTE}。\n- 2026-10-17前序D068：')
    after_title('项目文件索引.md',f'- 2026-10-17 D069：[已有模拟任务接入DML]({NOTE})、[程序及双击入口]({ENTRY})、[16类留出图](work/vpp_dml_project_trial_20261017/heldout_type_effects.png)。两次实跑/独立复核完成，当前配置未稳定胜过透明回归且预设零效应恢复不足；原数据/同事核心/六类实测保持。\n')
    p=ROOT/'work/vpp_dml_review_20261017/README.md'
    text=p.read_text(encoding='utf-8')
    text+=f'\n## 后续用户指定的本项目模拟数据试验\n\nD069已另行完成，见[接入入口](../vpp_dml_project_trial_20261017/README.md)和[结果](../process_notes/2026-10-17_已有模拟数据接入DML.md)。与上面同事自带模拟的复跑分开记录，不改D068原成绩。\n'
    p.write_text(text,encoding='utf-8')
    print('D069 recorded; original evidence and previous entries preserved.')

if __name__=='__main__':main()
