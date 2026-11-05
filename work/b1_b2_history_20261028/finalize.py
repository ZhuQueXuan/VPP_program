"""Update navigation and check package identity; no scientific output rewrite."""
import re
from io_utils import BASE,ROOT,RAW,read,write,sha

def main():
    path=ROOT/'docs/DECISION_LOG.md';text=path.read_text(encoding='utf-8');old=text.splitlines()[2]
    current='现用研究接续：D123（2026-10-28），完成B1前三次已完历史→B2可选消费及统计/PCA/非线性表示有限研究。验证14回C0/6统计，测试无稳定总体增量，AE重建改善未转化预测改善，默认D122和旧权重保持。20新种子/288000配对变体、用户/时点隔离及独立核验通过，313旧文件同。有限包结束不追分，正式时序深度/代表性机制/真实及90%口径、两小时学习→三小时连续迁移仍未完成；精度建议待确认留work，不自动B4/新实验。真实冻结/同事代码/会议报告及主稿未迁01保持。条目按ID追加在文末。'
    if '## D123｜' not in text:
        text=text.replace(old,current,1)+'''

## D123｜B1合法历史接入B2，有限表示研究无稳定增量后保留原模型

- 日期2026-10-28，用户同意按上一规划继续。实际调用原B1通用F0，显式1min/30min/驻留1格提取已完事件；B2新头消费前三历史6统计、PCA6或小型非线性6维表示，未把同次事后结果或群体因果作用当当前能力。主前冻结14新项及313旧项；20新种子×400用户12事件×3配对机制=288000变体/96000基础，用户240/80/80及目标3—6/7—8/9—11隔离，任务间180min、观测120min。
- 同类多项logit头，历史三法同6维，C0少6输入，不宣称总参数匹配；AE90→24→6→24→90/4752参数/固定60轮、训练历史独立拟合，未新增依赖。验证按MSE严格改善且Brier不差，14C0/6C1、PCA/AE0次。测试平均RMSE C0 .588489/统计.590853/PCA.591245/AE.591455/选择后.588948kW，选择MSE差+.000539724，20块95%[-.001061459,+.002140906]。服务Brier差−.000088702亦跨0，AE历史重建.028739→.022895未转化预测价值；原冻结B2诊断.579374kW，训练结构不同仅作诊断，不替换。
- 新api.predict_with_history为可选研究函数，固定rep0验证选C0，少历史回C0；未来/跨对象/不可得/缺测/域外历史不可用；许可和物理硬门、六结果输出一致、承诺null。默认D122模型/接口不改，本轮未把新模型导入B3主实验。30微型/独立46454259数值项/补667聚合及12实查询通过，数值项不是独立试验数；313旧项SHA同，原件data/B1_B2_history_v1_20261028，过程work/b1_b2_history_20261028。
- [结果与证据](../work/b1_b2_history_20261028/README.md)。生成+B1提取54.11s/训练验证落盘87.62s CPU，无新库/GPU/UI/上传/提交。本面板收口不扩历史/潜变量/网络求胜；不据负结果宣告历史无信息/深度无效/正式时序研究完成。精度口径建议待确认留work不迁01；代表性机制、真实证据、90%与B2两小时到B3三小时完整迁移保留，不自动B4或新主实验。真实冻结/74模型v15/同事代码/旧报告/全局主稿保持。
'''
        path.write_text(text,encoding='utf-8')
    f=read(BASE/'source_freeze.json');source_ok=all(sha(BASE/n)==h for n,h in f['source'].items());protected_ok=all(sha(ROOT/n)==h for n,h in f['protected'].items());assert source_ok and protected_ok
    # Generic B1 extractor has an original D106 code receipt, separate from D123 inherited protection list.
    original=read(ROOT/'work/b1_research_20261021/run_receipt.json')['code_sha256']['features.py'];actual=sha(ROOT/'work/b1_research_20261021/features.py');assert original==actual
    pf=read(BASE/'prediction_freeze.json');assert all(sha(BASE/n)==h for n,h in pf.items())
    checked=0
    for p in [BASE/'README.md',RAW/'README.md',BASE/'正式精度口径建议_待确认.md']:
        for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
            if target.startswith(('http:','https:','#')):continue
            assert (p.parent/target).resolve().exists(),target;checked+=1
    assert read(BASE/'independent_checks.json')['status']=='passed' and read(BASE/'supplement_checks.json')['status']=='passed'
    files={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in BASE.iterdir() if p.is_file() and p.name!='final_checks.json'}
    write(BASE/'final_checks.json',dict(status='passed',scientific_sources_match=source_ok,old_protected_files_unchanged=len(f['protected']),generic_B1_matches_original_D106_receipt=actual,predictions_and_selection_unchanged=True,local_links_checked=checked,files=files,raw_sha=sha(RAW/'observations.npz'),scope='finite optional history research only; original B2/B3 default retained; no real reliability/formal90 claim'))
    print('final checks passed',len(files),'package files,',checked,'local links',flush=True)

if __name__=='__main__':main()
