import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('/root/orbslam3_runs/research_eval/GrassGIS/46646/topological/keypoint_stats.csv')

fig, ax1 = plt.subplots(figsize=(10, 6))

color = 'tab:blue'
ax1.set_xlabel('Frame Index')
ax1.set_ylabel('Keypoint Count', color=color)
ax1.plot(df['frame'], df['count'], color=color, label='Extracted Keypoints')
ax1.axhline(y=1000, color='r', linestyle='--', label='Target (1000)')
ax1.tick_params(axis='y', labelcolor=color)
ax1.legend(loc='upper left')

ax2 = ax1.twinx()
color = 'tab:green'
ax2.set_ylabel('minThFAST Threshold', color=color)
ax2.plot(df['frame'], df['min_th'], color=color, label='minThFAST')
ax2.tick_params(axis='y', labelcolor=color)
ax2.set_ylim(0, 25)
ax2.legend(loc='upper right')

plt.title('Adaptive PID Controller: Keypoint Targeting vs Threshold')
fig.tight_layout()
plt.savefig('pid_evaluation.png')
print("Saved PID evaluation plot to pid_evaluation.png")