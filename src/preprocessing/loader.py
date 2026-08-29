"""
src/preprocessing/loader.py

Loads the NSL-KDD dataset and assigns the 41 feature column names + label column.
"""

import pandas as pd

# The 41 NSL-KDD feature names, in order, followed by the label and difficulty columns.
COLUMN_NAMES = [
    "duration", "protocol_type", "service", "flag", "src_bytes", "dst_bytes",
    "land", "wrong_fragment", "urgent", "hot", "num_failed_logins", "logged_in",
    "num_compromised", "root_shell", "su_attempted", "num_root", "num_file_creations",
    "num_shells", "num_access_files", "num_outbound_cmds", "is_host_login",
    "is_guest_login", "count", "srv_count", "serror_rate", "srv_serror_rate",
    "rerror_rate", "srv_rerror_rate", "same_srv_rate", "diff_srv_rate",
    "srv_diff_host_rate", "dst_host_count", "dst_host_srv_count",
    "dst_host_same_srv_rate", "dst_host_diff_srv_rate", "dst_host_same_src_port_rate",
    "dst_host_srv_diff_host_rate", "dst_host_serror_rate", "dst_host_srv_serror_rate",
    "dst_host_rerror_rate", "dst_host_srv_rerror_rate",
    "label", "difficulty_level"
]


def load_nsl_kdd(filepath: str) -> pd.DataFrame:
    """
    Load an NSL-KDD file (e.g. KDDTrain+.txt or KDDTest+.txt) into a DataFrame
    with proper column names.
    """
    df = pd.read_csv(filepath, header=None, names=COLUMN_NAMES)
    return df


# 5-class mapping: raw NSL-KDD labels -> Normal / DoS / Probe / R2L / U2R
ATTACK_CATEGORY_MAP = {
    "normal": "Normal",

    # DoS
    "back": "DoS", "land": "DoS", "neptune": "DoS", "pod": "DoS", "smurf": "DoS",
    "teardrop": "DoS", "mailbomb": "DoS", "apache2": "DoS", "processtable": "DoS",
    "udpstorm": "DoS",

    # Probe
    "ipsweep": "Probe", "nmap": "Probe", "portsweep": "Probe", "satan": "Probe",
    "mscan": "Probe", "saint": "Probe",

    # R2L (Remote to Local)
    "ftp_write": "R2L", "guess_passwd": "R2L", "imap": "R2L", "multihop": "R2L",
    "phf": "R2L", "spy": "R2L", "warezclient": "R2L", "warezmaster": "R2L",
    "sendmail": "R2L", "named": "R2L", "snmpgetattack": "R2L", "snmpguess": "R2L",
    "xlock": "R2L", "xsnoop": "R2L", "worm": "R2L", "httptunnel": "R2L",

    # U2R (User to Root)
    "buffer_overflow": "U2R", "loadmodule": "U2R", "perl": "U2R", "rootkit": "U2R",
    "ps": "U2R", "sqlattack": "U2R", "xterm": "U2R",
}


def add_attack_category(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a 'attack_category' column mapping each raw label to one of the 5
    target classes: Normal, DoS, Probe, R2L, U2R.
    """
    df = df.copy()
    df["attack_category"] = df["label"].map(ATTACK_CATEGORY_MAP)

    # Catch any label not in the map (dataset sometimes has a few rare/new attack types)
    unmapped = df["attack_category"].isna().sum()
    if unmapped > 0:
        print(f"Warning: {unmapped} rows had unmapped labels. Inspect df['label'].unique().")

    return df


if __name__ == "__main__":
    train_df = load_nsl_kdd("data/raw/KDDTrain+.txt")
    train_df = add_attack_category(train_df)

    print(train_df.shape)
    print(train_df.head())
    print(train_df["attack_category"].value_counts())