"""Render the verified simulation run and its field-data boundary offline."""
from html import escape
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def read(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


def chart(dose, estimated, truth):
    high = max(max(estimated), max(truth), 120) * 1.12
    low = min(min(estimated), min(truth), 0) - 15

    def xy(a, y):
        return 62 + 630 * (a - dose[0]) / (dose[-1] - dose[0]), 258 - 215 * (y - low) / (high - low)

    def trace(values, color):
        points = ' '.join(f'{x:.2f},{y:.2f}' for x, y in (xy(a, v) for a, v in zip(dose, values)))
        return f'<polyline points="{points}" stroke="{color}" stroke-width="3" fill="none"/>'

    labels = []
    for a in (0.4, 0.8, 1.2, 1.6, 2.0):
        x, _ = xy(a, 0)
        labels.append(f'<line x1="{x}" y1="43" x2="{x}" y2="258" stroke="#dce7ed"/>'
                      f'<text x="{x}" y="282" text-anchor="middle">{a:.1f}</text>')
    for tick in sorted(set([0, 120] + list(range(200, int(high), 100)))):
        _, y = xy(.4, tick)
        labels.append(f'<line x1="62" y1="{y}" x2="692" y2="{y}" stroke="#cbdce6"/>'
                      f'<text x="54" y="{y+4}" text-anchor="end">{tick}</text>')
    return ('<svg viewBox="0 0 720 315" role="img" aria-label="补偿提高后的有效减载时长增量。'
            '对照现用算法与同批模拟真值。"><text x="16" y="22">平均多调的秒数</text>'
            + ''.join(labels) + trace(truth, '#94600a') + trace(estimated, '#096472')
            + '<text x="692" y="307" text-anchor="end">事前补偿（元／千瓦时）</text></svg>')


def main():
    raw, comparison, decision, target = map(read, ('physical.json', 'confirmation.json', 'decision.json', 'target_check.json'))
    q = raw['query']
    curve = q['mean_curve']['curve']
    stats = comparison['comparisons'][str(decision['selected_alpha'])]
    rows = []
    for name, label in [('curve_rmse', '总体补偿曲线误差（秒）'), ('subgroup_rmse', '两组补偿效果差异误差（秒）'),
                        ('derivative_rmse', '每增加单位补偿的效果误差（秒／金额单位）')]:
        old, new = stats[name]['paired_means']
        rows.append(f'<tr><td>{label}</td><td>{old:.2f}</td><td>{new:.2f}</td><td>{stats[name]["paired"]} 组</td></tr>')
    estimate = raw['example']['contrasts'][1]
    example_index = min(range(len(raw['grid'])), key=lambda i: abs(raw['grid'][i]-raw['example']['incentive_values'][1]))
    lower, upper = (q['mean_curve']['inference'][key][example_index] for key in ('lower', 'upper'))
    crossing = q['target_threshold']['first_point_crossing']
    crossing_text = (f'首次达到目标的点估计是 {crossing:.3f} 元／千瓦时。' if crossing is not None
                     else '在这段报价范围内，点估计未达到目标。')
    shape = raw['errors']['effective_response_refined']
    base = raw['errors']['cpop']
    physical_rows = ''.join(f'<tr><td>{label}</td><td>{base[k]["mae"]:.2f}</td>'
                            f'<td>{shape[k]["mae"]:.2f}</td><td>{shape[k]["n"]}</td></tr>'
                            for k, label in [('cumulative', '累计时长'), ('longest', '最长连续时长')])
    learned = [r for r in raw['graph_scores'].values() if r['status'] == 'ok']
    found = ', '.join(f'{r["true_adjacencies"]}/{r["true_adjacencies"]+r["missed_adjacencies"]}' for r in learned)
    guard = read('demo_checks.json')['target_decision']
    guard_text = {'reached': '采样范围支持达到目标', 'below': '采样范围支持低于目标', 'uncertain': '证据不足'}[guard]
    p, g = target['point'], target['guarded']
    wins = len(stats['winning_blocks'])
    stress = read('process_confirmation.json')['stats']
    strong = stress['strong']['effective_response_refined']
    weak = stress['near_threshold']['cpop']
    downstream = read('demo_checks.json')['curve_rmse_by_extractor']
    page = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>充电桩调节与补偿演示</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f1f5f7;color:#17323e;font:16px/1.65 system-ui,"Microsoft YaHei",sans-serif}}main{{max-width:1000px;margin:auto;padding:28px 20px}}h1{{font-size:clamp(28px,5vw,45px);margin:4px 0}}h2{{font-size:22px;margin:0 0 12px}}p{{margin:10px 0}}section,header{{background:white;padding:22px;border:1px solid #d5e3e9;border-radius:12px;margin-bottom:16px}}header{{background:#103843;color:white}}a{{color:#086270}}strong{{font-weight:700}}small{{font-size:14px}}.badge{{color:#f5d58d}}.metric{{font-size:clamp(25px,4vw,40px);line-height:1.25;color:#086270}}.table{{overflow:auto}}table{{width:100%;border-collapse:collapse;min-width:540px}}th,td{{padding:8px;text-align:left;border-bottom:1px solid #dce7ed}}th{{background:#eaf3f5}}svg{{width:100%;height:auto;font-size:13px;fill:#243f4b}}.legend{{display:flex;gap:24px;flex-wrap:wrap}}.blue{{color:#096472}}.gold{{color:#94600a}}
</style></head><body><main>
<header><small class="badge">研究点一 · 单一资源 · 模拟演示</small><h1>补偿提高后，充电桩能多调多久？</h1><p>半小时调节任务，请求少充 1.5 kW。模拟事前补偿、车辆状态、参考功率和实际功率，覆盖 {raw['events']} 个任务与 {raw['users']} 名模拟用户。</p></header>
<section><h2>一次报价比较</h2><p class="metric"><strong>{estimate:+.1f} 秒</strong></p>
<p>从 {curve['reference_incentive']:.2f} 提高到 {raw['example']['incentive_values'][1]:.2f} 元／千瓦时，现用方法估计同一批模拟对象的平均累计有效减载时长变化。有效时长按同一任务窗口和减载标准计量。</p>
<p>这一个报价对比的模拟真值为 {raw['truth'][example_index]:.1f} 秒。条件采样带为 {lower:.1f} 至 {upper:.1f} 秒，反映固定辅助模型后的抽样波动。</p>
<p class="legend"><span class="blue">● 现用算法估计</span><span class="gold">● 同批模拟真值</span></p>
{chart(raw['grid'],curve['contrasts'],raw['truth'])}
<p>模拟目标是平均多调 120 秒。{escape(crossing_text)}结合现有采样带，演示判断为<strong>{guard_text}</strong>。这个判断只覆盖本次模拟查询的金额网格。</p></section>
<section><h2>各环节怎么接</h2><ol>
<li>从参考和实际功率量出每笔任务的累计有效时长。需要连续性时，可查最长连续时长。</li>
<li>按事前需求与离站余量核同类对象，再比较事前报价。结构诊断在本次模拟中找对的已知连接数为 {escape(found)}，按 FCI、PC 顺序列出。</li>
<li>任务考核中断或恢复时，展开真实充电过程案例。可在同一时间轴核对限额和实测功率。<a href="../b1_temporal_ev_demo_20261104/index.html">打开三例实测曲线</a></li>
<li>估计补偿增加的总体效果。此原始功率队列的分组报价支持不足，分组的误差比较用下方另行生成的模拟队列。</li>
<li>给定 120 秒目标后，结合点估计和证据范围报告达标、低于目标或证据不足。</li>
</ol></section>
<section><h2>同一批数据上的误差</h2>
<p>原始功率链使用新模拟，计量间隔 10 秒。时长误差单位为秒。</p>
<div class="table"><table><thead><tr><th>结果</th><th>原 CPOP</th><th>现用提取器</th><th>现用可测数</th></tr></thead><tbody>{physical_rows}</tbody></table></div>
<p>再用 48 笔参照已知、信号清楚的新模拟核对，现用提取器的两项误差为 {strong['cumulative_mae']:.2f} 秒和 {strong['longest_mae']:.2f} 秒，原 CPOP 两项仍接近零。另 48 笔同时接近判定线且噪声更大，原 CPOP 的两项误差为 {weak['cumulative_mae']:.2f} 秒和 {weak['longest_mae']:.2f} 秒，现用提取器超出适用范围。</p>
<p>把两种时长分别送入同一补偿估计器，原始功率队列的曲线误差分别为 {downstream['cpop']:.2f} 秒和 {downstream['effective_response_refined']:.2f} 秒。单笔时长的准确度和总体曲线的误差分别验收。</p>
<p>补偿比较另用六个新模拟批次、共 24 组。候选合并样本拟合再按事前条件分组。平均误差下降，总体曲线仅 {wins}/6 批改善，稳定性门槛为 4/6。演示采用现用连续方法。</p>
<div class="table"><table><thead><tr><th>指标</th><th>现用</th><th>研究候选</th><th>共同可评</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p>另用 48 组新模拟检验达标判断。只看点估计错 {p['wrong']} 组。加入证据范围后给出 {g['decisions']} 个明确判断，其中错 {g['wrong']} 组，另 {48-g['decisions']} 组标为证据不足。</p></section>
<section><h2>现场数据覆盖到哪里</h2><p>ACN 的真实记录可核对限额变化和功率跟随。当前可用的充电任务缺少能与响应对上的事前补偿，页面中的补偿增量、分组差异和目标判断均来自模拟。</p>
<p><a href="README.md">复算说明与证据表</a> · <a href="physical.json">原始功率链结果</a> · <a href="confirmation.json">同条件比较明细</a></p></section>
</main></body></html>'''
    (HERE / 'index.html').write_text(page, encoding='utf-8')


if __name__ == '__main__':
    main()
