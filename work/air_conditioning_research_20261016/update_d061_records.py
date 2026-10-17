"""Maintain concise process/decision/data/navigation entries; no handoff."""
from common import *
v=load(BASE/'runs/HIL_DIAGNOSTIC_01/verification.json');assert v['status']=='passed'
d=load(BASE/'runs/HIL_DIAGNOSTIC_01/summary.json');s=load(BASE/'runs/SPLITSMART_QA_02/summary.json')
assert s['rows']==1092 and s['backward']==88 and s['numeric_fields']['Real_Power']['nonempty']==0
p=sha(BASE/'hil_diagnostic_protocol_v1.json');assert p=='bb06fc5d7cc3b5a257bed44ef041c7bfaae46e959aed87387e3a40c1295e954f'
candidate={
 'decision':'D061','source_metadata_only':True,
 'SHIFDR':{'catalog_url':'https://openenergyhub.ornl.gov/explore/dataset/shifdr-sub-metered-hvac-implemented-for-demand-response/','saved_catalog_sha256':sha(BASE/'downloads/CONTROL_CANDIDATE_01/shifdr_catalog.html'),'catalog_has_records':False,'catalog_attachments':[],'primary_collection_url':'https://deepblue.lib.umich.edu/data/collections/vh53ww273?locale=en','primary_collection_web_access':'one403; stopped, no access bypass','license_boundary':'ORNL catalog labels Open Database License; underlying subset license and files unverified, not inherited automatically','raw_downloaded':False,'admitted':False},
 'dual_zone_experimental':{'catalog_url':'https://data.mendeley.com/datasets/7tzkdhgpfs/1','doi':'10.17632/7tzkdhgpfs.1','published':'2026-08-18','saved_catalog_sha256':sha(BASE/'downloads/CONTROL_CANDIDATE_01/mpc_experiment_catalog.html'),'catalog_claim':'dual-zone experimental chamber,5min indoor/outdoor temperature/solar/HVAC smart-meter power','license_catalog':'CC-BY-4.0','raw_downloaded':False,'paired_paper_verified':False,'admitted':False,'next':'Inspect primary file list/dictionary/paired manuscript and clock/electric-meter object first; if suitable, freeze simple thermal baseline before errors. Do not start distributed MPC or infer second-level response from5min data.'},
 'not_implemented':'No advanced control, no downloaded source code execution or fitted new model.'
}
cp=BASE/'control_candidate_status_v1.json';assert not cp.exists();dump(cp,candidate)
diagnostic=f'''D060误差已见后的描述性诊断，不是新盲测或成功标准。汇总前固定[hil_diagnostic_protocol_v1.json](../work/air_conditioning_research_20261016/hil_diagnostic_protocol_v1.json)，SHA256 `{p}`。研究代理定义为相邻1秒外机实测P变化绝对值≥500W，分析其±60秒并集与其余全部行；阈值系事后选定，不是真实压缩机启停/两档/指令标签。5原文件341639行全部保留，共312个观测跃迁；0拟合、0时间平移/滤波/删点，D060系数与原130256评价预测不变。'''
finding='''原两评价实验130256点，8368点（6.4243%）在上述窗口内，贡献M_TEMP绝对误差25.7904%、平方误差72.2844%；窗口内MAE330.364722W/RMSE602.659705W，其余121888点65.261298/97.778301W。不能以平方误差占比说成72%事件失败或因果解释。105°F的其余41049点B_COP→M_TEMP仍MAE81.035878→86.407475W、RMSE111.646569→122.401767W，故高温退步并非只发生在跳变附近，不能靠删瞬态或仅认稳态挽救原门槛；85°F跃迁窗口RMSE也稍退步，全部表保留。两个评价实验另有82点Q≤0且总电P≥1000W，仅为同期信号不一致的描述，不诊断故障/延迟。14字段无直接档位/启停指令；严格1秒文件时钟不等于物理同步标定。旧最差点±180秒361原行另存供追溯，不当代表样本。'''
source='''新候选[SplitSmart原始目录5971](https://data.openei.org/submissions/5971)及准确CC-BY-4.0许可、4个房间context、最小C108AC01完整CSV已取；作者Kaushik/Naik、BITS Pilani Goa。完整CSV226458字节/SHA256 `6a2a622d7196f0f90fb18041b82c43cbb56c958c0e8dd085769b4944c3bc2b79`，1092行、2023-06-05至08-31，显式+00:00。原序88处倒序/无重复，中位相邻差161.418935秒、最大2663810.286229秒；_created与测量时刻差有369负值，不能作控制延迟。Real_Power全空，room_temp仅24.8/24.9/25.0三个值，未确认传感器/单位/采样和更新语义。其余8数据文件仅各16384字节HTTP206前缀（非完整下载/QA）；九文件同14字段表头，无明确设定温度、指令、档位或送达时点。不能推称其余8文件功率也全空，不能用UI或UI×PF补成独立实测有功真值。4context说明同室1/2/3台空调，人数/时段是静态描述，不作实时占用。该来源暂不准入当前控制响应/独立电功率与因果温度验证，不全盘判其无其他价值；不获取其余大文件或拟合。下载SHA仅本地身份，无发布者独立校验和。'''
verification='''HIL_DIAGNOSTIC_01/02四科研产物字节相同。verify_hil_diagnostic.py独立stdlib原CSV/datetime/最近事件bisect（运行器为pandas/差分区间并集），重核341639行标记、312跃迁、全部130256旧预测及361上下文，6801数值检查通过；旧预测最大差1.14e-12W，MAE/RMSE最大差2.28e-13W。SplitSmart完整小文件另用pandas独立读数/时钟核对1092行、88倒序、功率全空及温度3值。QA_01文字曾误写“温度恒定”，原数值表始终为3值；QA_02更正文字、QA_01历史保留，数据/指标未改，不作科学调参或准入放宽。'''
nextstep='''后续数据线索仅做官方目录核查：ORNL SHIFDR目录实际无附件/records，其所链Michigan原发布集一次403后停止，未取原数据/子集许可；Mendeley双区试验10.17632/7tzkdhgpfs.1目录称5分钟实测温度/智能电表功率，尚无原文件/字典/配套论文核验，不宣称合格。当前下一单项先核Mendeley原文件、设备计量对象、时间字段及论文，再决定简单热响应baseline；不会因源名称含MPC就开发高级控制，也不以5分钟数据验证秒级时延。状态与目录证据见control_candidate_status_v1.json。空调基础包仍未验收，不建最终成果目录；D059/D060失败、原三类成果保持，P1/103未通过。不更新handoff/教师稿、不新建正式报告、整合或GPU训练。'''
body='\n\n'.join('- '+x for x in (diagnostic,finding,source,verification,nextstep))
short='''2026-10-16现用D061：空调完成事后误差分布诊断及SplitSmart用途核查。外机相邻功率跃迁≥500W的±60s窗口占原评价6.4243%点/贡献M_TEMP平方误差72.2844%；105°F其余点仍退步，不能靠删瞬态补分。阈值事后选择，只描述、不认定真实启停/档位/时延，0新拟合，原预测/失败不变。新来源仅1完整小CSV1092行/88倒序/Real_Power全空＋其余8文件前缀，缺控制标签，当前用途不准入；不外推全套质量。独立341639标记/312跃迁/130256旧预测/6801数值及4产物复跑通过。卡DC-20261016-07，空调未验收/不建最终目录。下一单项核Mendeley双区5分钟实测数据的原文件/字典与论文，仅候选，不启动MPC；SHIFDR原发布一次403停止。原三类成果、handoff/教师稿保持，不整合/高级分支/GPU，P1/103未过。'''
changes={}
def edit(name,fn):
    path=ROOT/name;txt=path.read_text(encoding='utf-8');assert 'D061' not in txt,name;changes[path]=fn(txt)
edit('docs/DECISION_LOG.md',lambda t:t+'\n\n## D061｜空调事后跃迁误差分布与SplitSmart用途不准入\n\n- 日期：2026-10-16；状态：诊断/候选核查完成，非资源基础包验收。\n\n'+body+'\n\n- [过程入口](../work/air_conditioning_research_20261016/README.md)；现用卡DC-20261016-07仅新增描述/候选状态，D060/059原科学协议保持。\n')
card='## 空调：事后误差分组与SplitSmart候选核查（D061）\n\n'+'\n\n'.join('- '+x for x in (diagnostic,source))+'\n\n- 现用07新增诊断/候选用途状态，不建立新预测样本或放宽旧实验准入。SplitSmart现用QA_02更正QA_01的“恒定”文字，数值始终3值；其他8文件仍只有前缀，不据此全量准入。Mendeley/SHIFDR仅目录候选，见过程入口及control_candidate_status_v1.json。\n\n'
edit('docs/DATA_CARD.md',lambda t:t.replace('卡版本：DC-20261016-06','卡版本：DC-20261016-07',1).replace('## 空调：独立NLR HIL设备同期电功率重建限定准入（D060）',card+'## 空调：独立NLR HIL设备同期电功率重建限定准入（D060）',1))
exp='## DIAG-HVAC-20261016｜事后跃迁误差分布及候选QA（D061）\n\n'+'\n\n'.join('- '+x for x in (diagnostic,finding,verification))+'\n\n- 实际运行：SPLITSMART_PREVIEW_01全7项/HEADERS_01八前缀→QA_01/02（数值不变、文字更正）；freeze_hil_diagnostic.py→HIL_DIAGNOSTIC_01/02→verify_hil_diagnostic.py；CONTROL_CANDIDATE_01仅两目录。没有新拟合/新盲测或容量实验。原D060完整门槛仍失败，下一项先做新源准入。\n\n'
edit('docs/EXPERIMENT_LOG.md',lambda t:t.replace('## BL-HVAC-HIL-POWER-20261016',exp+'## BL-HVAC-HIL-POWER-20261016',1))
for name in ['outputs/ROADMAP_v2.md','outputs/第一阶段两周执行计划_v2_20261013.md']:
    edit(name,lambda t:t.replace('最新执行（2026-10-16，D060）','最新执行（D061）：'+short+'\n\n前序执行（2026-10-16，D060）',1).replace('现用D060：','现用D061：完成事后描述/候选QA，当前先核新Mendeley原文件/字典与论文，空调未验收、不改原失败。以下D060为历史时点。\n\n前序D060：',1).replace('当前按D060完成新HIL来源/同期功率首轮比较，补动态状态/同步与独立验证依据','当前按D061完成事后描述/候选QA，先核新Mendeley原文件/字典与论文以补独立验证依据',1))
edit('AGENTS.md',lambda t:t.replace('先读D060 HIL','先读D061事后跃迁诊断/候选用途不准入及新源接续，再读D060 HIL',1).replace('- 2026-10-16现用D060：','- '+short+'\n- 2026-10-16前序D060：',1))
edit('项目文件索引.md',lambda t:t.replace('\n\n','\n\n- '+short+'[空调过程入口](work/air_conditioning_research_20261016/README.md)、[事后描述协议](work/air_conditioning_research_20261016/hil_diagnostic_protocol_v1.json)。\n\n',1).replace('2026-10-16现用D060','2026-10-16前序D060',1))
edit('resource_research_results/README.md',lambda t:t+'\n2026-10-16 D061：空调事后诊断与新候选用途核查完成，原模型失败保持，尚未达到有限验收；全部诊断/下载/核验留[过程目录](../work/air_conditioning_research_20261016/README.md)，不增加最终类型目录。\n')
edit('work/process_notes/2026-10-16_空调资源研究.md',lambda t:t.replace('现用D060（D059前序保留）','现用D061（D060/059前序保留）',1)+'\n\n## D061｜事后误差分布、候选用途与新源接续\n\n'+body+'\n')
intro='''## 当前D061：事后误差分布与新候选用途核查

这一轮没有拟合或调参，空调基础包仍未验收。

- [事后描述协议](hil_diagnostic_protocol_v1.json)在D060误差已见后固定，SHA256 `'''+p+'''`；≥500W外机相邻跃迁及±60s窗口是研究代理，不是真启停/档位或调度时延。原5文件全341639行、312跃迁；旧130256评价预测和原门槛不变。
- 原评价8368点（6.4243%）在窗口内，贡献M_TEMP平方误差72.2844%；105°F其余41049点MAE81.035878→86.407475W、RMSE111.646569→122.401767W仍退步。不能删瞬态补分或把非窗口命名真实稳态；82点Q≤0且总P≥1000W也保留，不能定故障原因。最差点±180s原361行在worst_context.csv，只作选定案例。
- HIL_DIAGNOSTIC_01/02四科研产物相同；[独立核验](runs/HIL_DIAGNOSTIC_01/verification.json)stdlibCSV/datetime/bisect核341639标记、312跃迁、130256旧预测、6801数值通过，旧预测最大差1.14e-12W。执行`run_hil_diagnostic.py --run-id <新的唯一ID>`可复跑；freeze/verify/QA均拒覆盖旧证据。
- [SplitSmart官方目录](https://data.openei.org/submissions/5971)为新候选，完整4context＋最小CSV1092行，另8文件仅各16KiB前缀，不能称全量QA。九文件字段未含明确指令/设定/档位；已核小CSV原序88倒序，Real_Power全空、room_temp24.8—25.0共3值。完整文件、许可与全部前缀身份保存，当前控制/独立电功率/因果温度用途不准入，不推断其他8文件功率也全空、不补造UI×PF。现用SPLITSMART_QA_02：QA_01的“恒定”文字已纠正，原数值一直3值。
- [后续候选状态](control_candidate_status_v1.json)：SHIFDR目录无附件，原Michigan集一次403后停止；Mendeley10.17632/7tzkdhgpfs.1目录称双区5分钟实测温度/智能电表P，原文件/字典/配套论文未取或核验。下一单项核其原始来源与用途，合适后才固定简单热响应baseline；不因源标题含MPC而启动高级控制，不用5分钟数据验秒级时延。

现用卡DC-20261016-07。原三类最终包、D059/D060原科学文件/失败保持，不建空调最终目录，不整合、GPU训练或更新handoff/教师稿。以下按原时点追溯。

'''
edit('work/air_conditioning_research_20261016/README.md',lambda t:t.replace('现用决定D060','现用决定D061',1).replace('## 当前D060：新HIL设备电表准入与同期功率比较',intro+'## 前序D060：新HIL设备电表准入与同期功率比较',1))
# Precompute every edit before writing any file. No deletion, archive or overwrite of results.
for path,txt in changes.items():path.write_text(txt,encoding='utf-8')
print('Updated',len(changes),'existing records; D061 descriptive work only, no handoff/final HVAC package.')
