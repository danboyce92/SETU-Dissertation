import pandas as pd
from scipy import stats

df = pd.read_csv('./merged_sync.csv')

win10 = df[df.OS == 'Win10']['Smeared%']
win11 = df[df.OS == 'Win11']['Smeared%']

# Shapiro-Wilk check
w1, p1 = stats.shapiro(win10)
w2, p2 = stats.shapiro(win11)

print("Shapiro-Wilk normality test")
print(f"  Win10 (n={len(win10)}): W={w1:.4f}, p={p1:.6f}  {'-> NOT normal' if p1 < .05 else '-> normal'}")
print(f"  Win11 (n={len(win11)}): W={w2:.4f}, p={p2:.6f}  {'-> NOT normal' if p2 < .05 else '-> normal'}")
print()

# Mann-Whitney U
U, p = stats.mannwhitneyu(win10, win11, alternative='two-sided')

print("Mann-Whitney U test")
print(f"  U = {U:.1f}, p = {p:.6f}")
print(f"  Win10 median = {win10.median():.2f}%   Win11 median = {win11.median():.2f}%")
