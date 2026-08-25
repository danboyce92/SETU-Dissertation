import pandas as pd
from scipy import stats

df = pd.read_csv('./merged_async.csv')

print("Pearson and Spearman correlation: Smeared vs VAD Inconsistencies")
print("(Async dataset, computed per OS x RAM tier cell, pressure levels pooled)")
print()

for os_name in ['Win10', 'Win11']:
    for ram in ['8Gb', '16Gb', '32Gb']:
        sub = df[(df.OS == os_name) & (df.RAM == ram)]

        if len(sub) < 2:
            print(f"{os_name} {ram}: skipped (n={len(sub)}, no data)")
            print()
            continue

        r, p_r = stats.pearsonr(sub['Smeared%'], sub['MediumLarge%'])
        rho, p_rho = stats.spearmanr(sub['Smeared%'], sub['MediumLarge%'])

        print(f"{os_name} {ram} (n={len(sub)})")
        print(f"  Pearson r  = {r:+.3f}   p = {p_r:.4f}")
        print(f"  Spearman rho = {rho:+.3f}   p = {p_rho:.4f}")
        print()
