"""Plot only old saved diagnostic scores; no model or simulator imports."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

HERE=Path(__file__).resolve().parent
font=Path("C:/Windows/Fonts/msyh.ttc")
if font.exists():
    font_manager.fontManager.addfont(str(font))
    plt.rcParams["font.family"]=font_manager.FontProperties(fname=str(font)).get_name()
plt.rcParams["axes.unicode_minus"]=False


def read(name):
    with (HERE/name).open(encoding="utf-8-sig",newline="") as fp:
        return list(csv.DictReader(fp))


blocks=read("block_summary.csv")
cohorts=read("cohort_diagnosis.csv")
seeds=[r["seed"] for r in blocks]
kinds=["randomized","observed_confounding","nonmonotone","zero_effect"]
fig,(ax,bx)=plt.subplots(1,2,figsize=(12.4,4.5),gridspec_kw={"width_ratios":[1,1.3]})
fig.patch.set_facecolor("#fbfbfa")
pos=np.arange(6)
ax.barh(pos-.17,[float(r["contrast_delta_s"]) for r in blocks],height=.32,label="总体补偿增量",color="#315b83")
ax.barh(pos+.17,[float(r["group_difference_delta_s"]) for r in blocks],height=.32,label="组间作用差异",color="#bd6b37")
ax.axvline(0,color="#333",lw=.7)
ax.set_yticks(pos,[s[-3:] for s in seeds])
ax.invert_yaxis()
ax.set_xlabel("候选减原DR的RMSE（秒）；负值更准")
ax.set_ylabel("独立种子块（90412…）")
ax.set_title("总体仅2/6块改善，组差5/6块改善",fontsize=12)
ax.legend(loc="lower left",fontsize=9,frameon=False)
values=np.array([[float(next(r["contrast_delta_s"] for r in cohorts
                           if r["seed"]==s and r["mechanism"]==k)) for s in seeds] for k in kinds])
limit=max(abs(values.min()),abs(values.max()))
bx.imshow(values,cmap="RdBu_r",vmin=-limit,vmax=limit,aspect="auto")
bx.set_xticks(range(6),[s[-3:] for s in seeds])
bx.set_yticks(range(4),["随机补偿","观测补偿","非单调","零作用"])
bx.set_xlabel("独立种子块（90412…）")
bx.set_title("24组总体增量误差差值（秒）",fontsize=12)
for i in range(4):
    for j in range(6):
        bx.text(j,i,f"{values[i,j]:+.1f}",ha="center",va="center",
                color="white" if abs(values[i,j])>limit*.6 else "#1f2730",fontsize=10)
fig.text(.03,.01,"旧确认只作诊断。同种子四机制配对；未训练、未调参。总体绝对水平未保存。",fontsize=9,color="#555")
fig.tight_layout(rect=(0,.045,1,1))
fig.savefig(HERE/"diagnosis.png",dpi=170)
