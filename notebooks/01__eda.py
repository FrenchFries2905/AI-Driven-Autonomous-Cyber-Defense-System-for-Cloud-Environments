# %% [markdown]
# # NSL-KDD — Label Mapping + Exploratory Data Analysis

# %%
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

sys.path.append("../src")  # adjust if your notebooks/ folder is nested differently
from preprocessing.loader import load_nsl_kdd, add_attack_category

pd.set_option("display.max_columns", None)
sns.set_style("whitegrid")

# %% [markdown]
# ## 1. Load data

# %%
train_df = load_nsl_kdd("../data/raw/KDDTrain+.txt")
test_df = load_nsl_kdd("../data/raw/KDDTest+.txt")

print("Train shape:", train_df.shape)
print("Test shape:", test_df.shape)
train_df.head()

# %% [markdown]
# ## 2. Map raw attack labels into the 5 target classes
# (Normal, DoS, Probe, R2L, U2R) — using the mapping already defined in loader.py

# %%
train_df = add_attack_category(train_df)
test_df = add_attack_category(test_df)

# Confirm no rows were left unmapped
print("Unmapped rows (train):", train_df["attack_category"].isna().sum())
print("Unmapped rows (test):", test_df["attack_category"].isna().sum())

train_df[["label", "attack_category"]].sample(10, random_state=42)

# %% [markdown]
# ## 3. Class distribution

# %%
print("=== Train set class distribution ===")
print(train_df["attack_category"].value_counts())
print("\nAs percentage:")
print((train_df["attack_category"].value_counts(normalize=True) * 100).round(2))

# %%
plt.figure(figsize=(8, 5))
sns.countplot(
    data=train_df,
    x="attack_category",
    order=train_df["attack_category"].value_counts().index,
)
plt.title("Class Distribution — Training Set")
plt.xlabel("Attack Category")
plt.ylabel("Count")
plt.show()

# %% [markdown]
# Note: NSL-KDD is heavily imbalanced — Normal and DoS dominate, while U2R and R2L
# have very few samples. This matters later: accuracy alone won't tell the full story,
# so track per-class precision/recall (especially for U2R/R2L) in Phase 2 evaluation.

# %% [markdown]
# ## 4. Missing values

# %%
missing = train_df.isnull().sum()
missing = missing[missing > 0]

if missing.empty:
    print("No missing values found.")
else:
    print(missing)

# %% [markdown]
# NSL-KDD is typically clean (no NaNs) since it's a curated benchmark dataset —
# but always verify rather than assume, especially after any custom preprocessing.

# %% [markdown]
# ## 5. Outliers
# Focus on key numeric features known to have skewed distributions
# (duration, src_bytes, dst_bytes, count, srv_count).

# %%
numeric_cols = ["duration", "src_bytes", "dst_bytes", "count", "srv_count"]

train_df[numeric_cols].describe()

# %%
fig, axes = plt.subplots(1, len(numeric_cols), figsize=(20, 4))
for ax, col in zip(axes, numeric_cols):
    sns.boxplot(y=train_df[col], ax=ax)
    ax.set_title(col)
plt.tight_layout()
plt.show()

# %%
# Quantify outliers using the IQR method
def count_outliers_iqr(series: pd.Series) -> int:
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return ((series < lower) | (series > upper)).sum()

for col in numeric_cols:
    n_outliers = count_outliers_iqr(train_df[col])
    pct = round(n_outliers / len(train_df) * 100, 2)
    print(f"{col}: {n_outliers} outliers ({pct}%)")

# %% [markdown]
# Note: In network traffic data, "outliers" (huge src_bytes, long duration, etc.)
# are often genuine signal — some attack types produce extreme values by nature.
# Don't blindly remove them; this is why we scale (StandardScaler) rather than
# clip/drop in Phase 1, and let the Random Forest — which is robust to outliers —
# handle the rest in Phase 2.

# %% [markdown]
# ## 6. Categorical feature check
# protocol_type, service, flag will need encoding before model training (next step).

# %%
for col in ["protocol_type", "service", "flag"]:
    print(f"\n{col} — {train_df[col].nunique()} unique values:")
    print(train_df[col].value_counts().head(10))