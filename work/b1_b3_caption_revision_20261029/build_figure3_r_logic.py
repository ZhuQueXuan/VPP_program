from pathlib import Path
from html import escape
import json

work = Path(__file__).resolve().parent
out = work / 'report_markdown_assets' / 'figure-03-r-logic.svg'
parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="920" viewBox="0 0 1800 920">',
         '<rect width="1800" height="920" fill="white"/>',
         '<defs><marker id="arrow" markerWidth="12" markerHeight="10" refX="10" refY="5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L10,5 L0,10" fill="#405d73"/></marker><marker id="gray" markerWidth="12" markerHeight="10" refX="10" refY="5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L10,5 L0,10" fill="#7d8790"/></marker></defs>',
         '<g font-family="Microsoft YaHei, SimHei, sans-serif" fill="#203443">']

def text(x, y, value, size=26, anchor='start', bold=False, color=None):
    attr = f' font-weight="600"' if bold else ''
    if color:
        attr += f' fill="{color}"'
    parts.append(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}"{attr}>{escape(value)}</text>')

def box(x, y, width, height, lines, fill='#f6f8fa', stroke='#9aabb8', main=False):
    parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="7" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
    count = len(lines)
    first = y + height/2 - (count-1)*19 + 9
    for i, line in enumerate(lines):
        text(x+width/2, first+i*38, line, 25 if i==0 else 23, 'middle', main and i==0)

edges = []
def arrow(points, src, dst, kind='effect'):
    dash = ' stroke-dasharray="10 8"' if kind=='assignment' else ''
    gray = kind=='derived'
    color = '#7d8790' if gray else '#405d73'
    pts = ' '.join(f'{x},{y}' for x,y in points)
    parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="3" stroke-linejoin="round"{dash} marker-end="url(#{"gray" if gray else "arrow"})"/>')
    edges.append({'from':src,'to':dst,'type':kind})

text(45, 49, '（a）因素关系：累计响应时长 R 为主要分析结果', 30, bold=True)
arrow([(178,150),(178,105),(1300,105),(1300,275)], 'X','R')
arrow([(178,510),(178,560),(1300,560),(1300,385)], 'W','R')
arrow([(295,451),(925,451),(925,385)], 'W','A')
arrow([(295,205),(425,305)], 'X','D','assignment')
arrow([(295,425),(425,355)], 'W','D','assignment')
arrow([(675,330),(800,330)], 'D','A')
arrow([(1050,330),(1175,330)], 'A','R')
arrow([(1425,330),(1500,330)], 'R','S','derived')
box(60,150,235,110,['事前期限余量 X'])
box(60,400,235,110,['充电需求紧迫度 W'])
box(425,275,250,110,['补偿档位 D','低档 / 高档'])
box(800,275,250,110,['是否参加 A','补偿后的参加结果'])
box(1175,275,250,110,['累计响应时长 R','主要结果（秒）'],fill='#e7f0f7',stroke='#356e94',main=True)
box(1500,275,250,110,['辅助标记 S','S = I(R ≥ 600秒)'])
text(1462,253,'阈值转换',22,'middle',color='#687681')
text(400,610,'实线：声明的影响关系；虚线：非随机补偿分配路径；灰箭头：由 R 计算 S',24,color='#586c7c')
parts.append('<line x1="45" y1="648" x2="1755" y2="648" stroke="#dce3e9" stroke-width="2"/>')
text(45,698,'（b）计算流程：从功率曲线到补偿影响估计',30,bold=True)
arrow([(380,785),(465,785)],'curves','extract','data')
arrow([(815,785),(900,785)],'extract','estimate','data')
arrow([(1320,785),(1405,785)],'estimate','effect','data')
box(50,730,330,110,['参考与观测功率曲线','及请求窗口'])
box(465,730,350,110,['2.1 特征提取','提取累计时长 R（秒）'])
box(900,730,420,110,['2.2 补偿影响估计','输入 X、W、D、R','按 X、W 调整事前差异'])
box(1405,730,350,110,['高低补偿的平均作用','调整后的累计时长平均差'],fill='#e7f0f7',stroke='#356e94',main=True)
text(45,892,'上图表示结构假设，下图表示计算顺序；R 为以秒计的累计时长，S 为辅助二元标记。',24,color='#586c7c')
parts.append('</g></svg>')
out.write_text('\n'.join(parts),encoding='utf-8')
assert {(e['from'],e['to']) for e in edges if e['type']=='effect'} == {('X','R'),('W','R'),('W','A'),('D','A'),('A','R')}
(work/'figure3_r_logic_spec.json').write_text(json.dumps({'svg':str(out),'edges':edges,'main_outcome':'R','auxiliary_outcome':'S=I(R>=600s)','declared_structure_not_learned_complete_graph':True},ensure_ascii=False,indent=2),encoding='utf-8')
print(out)
