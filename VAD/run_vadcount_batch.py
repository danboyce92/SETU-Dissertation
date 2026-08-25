"""
Script for automation. Creates a master csv file with comparisons for all vadcount runs together.
Usage:
    python run_vadcount_batch.py
    (edit the CONFIG section below first)
"""

import csv
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_vadcounts import load_counts, tier_for_delta

# ============================== CONFIG ==============================
CONFIGURATION = "Win11_16Gb_2_A"

# Folder containing the RunXXX.vmem / RunXXX.raw pairs for ONE configuration.
# The folder's own name is parsed as OS_RAMTier_Pressure.
INPUT_FOLDER = rf"E:\Research\SharedFolder\Acquisitions\{CONFIGURATION}"

# Where the final combined results CSV is written.
OUTPUT_CSV = rf"E:\Research\Pipeline\VADResults\{CONFIGURATION}_vadcount_master.csv"

# Per-run vadcount.py CSV outputs are kept here (not deleted) as an audit
# trail, in case you need to double check a specific run later.
INTERMEDIATE_DIR = rf"E:\Research\Pipeline\VADResults\intermediate\{CONFIGURATION}"

# Full per-process comparison detail for each run is kept here (one CSV per
# run, e.g. Run001_comparison.csv). OUTPUT_CSV is the compact one-row-per-run
# summary; these are where the underlying process-level detail lives.
PER_RUN_DIR = rf"E:\Research\Pipeline\VADResults\per_run\{CONFIGURATION}"

# Path to vol.exe / vol.bat inside your Volatility3 venv's Scripts folder.
VOL_EXE = r"C:\Users\duff1\Documents\Volatility3\volenv\Scripts\vol.exe"

# Path to the folder containing your custom vadcount.py plugin.
PLUGIN_DIR = r"C:\Users\duff1\Documents\Volatility3\custom_plugins"

# Max seconds to let a single vol invocation run before giving up on that
# run and moving on to the next one. Increase if 32GB images are timing out.
TIMEOUT_SECONDS = 900

# =====================================================================


def parse_folder_metadata(folder):
    # Extract OS / RAMTier / Pressure / Variant from a folder name.

    name = Path(folder).name
    parts = name.split("_")
    if len(parts) not in (3, 4):
        raise ValueError(
            f"Folder name '{name}' doesn't match the expected "
            f"OS_RAMTier_Pressure[_Variant] pattern (e.g. Win10_8Gb_0 or Win10_8Gb_0_A)"
        )
    os_name, ram_tier, pressure = parts[0], parts[1], parts[2]

    variant = ""
    if len(parts) == 4:
        suffix = parts[3]
        variant = VARIANT_SUFFIXES.get(suffix.upper())
        if variant is None:
            raise ValueError(
                f"Folder name '{name}' has an unrecognised variant suffix "
                f"'{suffix}'. Known suffixes: {sorted(VARIANT_SUFFIXES)}"
            )

    return os_name, ram_tier, pressure, variant


# Maps a folder-name suffix (after the 3rd underscore) to a human-readable
# variant label used in the output CSVs. Add new entries here as needed.
VARIANT_SUFFIXES = {
    "A": "Async",
}


def find_run_pairs(folder):
    # Find matching RunXXX.vmem / RunXXX.raw pairs in folder, sorted by run number.
    folder = Path(folder)
    vmem_files, raw_files = {}, {}
    pattern = re.compile(r"^(Run\d+[A-Za-z]?)\.(vmem|raw)$", re.IGNORECASE)

    for f in folder.iterdir():
        if not f.is_file():
            continue
        m = pattern.match(f.name)
        if not m:
            continue
        run_id, ext = m.group(1), m.group(2).lower()
        (vmem_files if ext == "vmem" else raw_files)[run_id] = f

    run_ids = sorted(
        set(vmem_files) | set(raw_files),
        key=lambda r: int(re.search(r"\d+", r).group()),
    )

    pairs = []
    for run_id in run_ids:
        vmem, raw = vmem_files.get(run_id), raw_files.get(run_id)
        if vmem is None or raw is None:
            missing = "vmem" if vmem is None else "raw"
            print(f"  [WARN] Skipping {run_id}: no matching .{missing} file found")
            continue
        pairs.append((run_id, vmem, raw))
    return pairs


def run_vadcount(target_file, out_csv):
    # Run the vadcount.py plugin against a single .vmem or .raw file.
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        VOL_EXE,
        "-f", str(target_file),
        "-p", PLUGIN_DIR,
        "-r", "csv",
        "windows.vadcount.VadCountCheck",
    ]

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8",
        timeout=TIMEOUT_SECONDS, env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"vol exited {result.returncode} on {target_file.name}:\n{result.stderr}")
    out_csv.write_text(result.stdout, encoding="utf-8")


def compare_pair(run_id, os_name, ram_tier, pressure, variant, vmem_csv, raw_csv):

    # Compare one run's vmem/raw vadcount CSVs into a list of row dicts.
    vmem_counts = load_counts(vmem_csv)
    raw_counts = load_counts(raw_csv)
    all_pids = sorted(set(vmem_counts) | set(raw_counts))

    rows = []
    for pid in all_pids:
        vmem_row, raw_row = vmem_counts.get(pid), raw_counts.get(pid)
        base = {"RunID": run_id, "OS": os_name, "RAMTier": ram_tier, "Pressure": pressure,
                "Variant": variant, "PID": pid}

        # process present in one file only
        if vmem_row is None or raw_row is None:
            present = vmem_row or raw_row
            base.update({
                "Process": present["Process"],
                "VmemCount": "", "RawCount": "", "Delta": "",
                "Status": "MISSING FROM VMEM" if vmem_row is None else "MISSING FROM RAW",
                "Tier": "MISSING",
                "Error": present.get("Error", ""),
            })
            rows.append(base)
            continue

        vmem_count, raw_count = int(vmem_row["VadNodeCount"]), int(raw_row["VadNodeCount"])

        if vmem_count == -1 or raw_count == -1:
            combined_error = "; ".join(e for e in (vmem_row.get("Error", ""), raw_row.get("Error", "")) if e)
            base.update({
                "Process": vmem_row["Process"],
                "VmemCount": vmem_count if vmem_count != -1 else "",
                "RawCount": raw_count if raw_count != -1 else "",
                "Delta": "",
                "Status": "ERROR",
                "Tier": "ERROR",
                "Error": combined_error,
            })
            rows.append(base)
            continue

        delta = raw_count - vmem_count
        base.update({
            "Process": vmem_row["Process"],
            "VmemCount": vmem_count, "RawCount": raw_count, "Delta": delta,
            "Status": "MATCH" if delta == 0 else "MISMATCH",
            "Tier": tier_for_delta(abs(delta)),
            "Error": "",
        })
        rows.append(base)

    return rows


DETAIL_FIELDNAMES = ["RunID", "OS", "RAMTier", "Pressure", "Variant", "PID", "Process",
                     "VmemCount", "RawCount", "Delta", "Status", "Tier", "Error"]

SUMMARY_TIERS = ["MATCH", "SMALL", "MEDIUM", "LARGE", "ERROR", "MISSING"]


def write_detail_csv(rows, out_csv):

    # Write the full per-process comparison for one run to its own CSV.
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=DETAIL_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def summarize_run(run_id, os_name, ram_tier, pressure, variant, rows):

    # Collapse one run's per-process rows into a single summary row.
    total = len(rows)
    counts = {tier: 0 for tier in SUMMARY_TIERS}
    for row in rows:
        counts[row["Tier"]] += 1

    def pct(n):
        return round(100 * n / total, 2) if total else 0.0

    summary = {
        "RunID": run_id, "OS": os_name, "RAMTier": ram_tier, "Pressure": pressure,
        "Variant": variant, "TotalProcesses": total,
    }
    for tier in SUMMARY_TIERS:
        label = tier.capitalize()
        summary[f"{label}Count"] = counts[tier]
        summary[f"{label}Pct"] = pct(counts[tier])
    return summary


def write_master_csv(summary_rows, output_path):

    # Write the compact one-row-per-run master CSV.
    header = [
        "RunID", "OS", "RAMTier", "Pressure", "Variant", "TotalProcesses",
        "StableCount", "MediumCount", "LargeCount", "",
        "Stable%", "Medium%", "Large%", "",
        "ErrorCount", "MissingCount", "Error%", "Missing%",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for s in summary_rows:
            total = s["TotalProcesses"]
            stable_count = s["MatchCount"] + s["SmallCount"]
            stable_pct = round(100 * stable_count / total, 2) if total else 0.0
            writer.writerow([
                s["RunID"], s["OS"], s["RAMTier"], s["Pressure"], s["Variant"], total,
                stable_count, s["MediumCount"], s["LargeCount"], "",
                stable_pct, s["MediumPct"], s["LargePct"], "",
                s["ErrorCount"], s["MissingCount"], s["ErrorPct"], s["MissingPct"],
            ])


def main():
    os_name, ram_tier, pressure, variant = parse_folder_metadata(INPUT_FOLDER)
    variant_msg = f", Variant={variant}" if variant else ""
    print(f"Folder metadata: OS={os_name}, RAMTier={ram_tier}, Pressure={pressure}{variant_msg}")

    pairs = find_run_pairs(INPUT_FOLDER)
    print(f"Found {len(pairs)} run pair(s) in {INPUT_FOLDER}")
    if not pairs:
        print("Nothing to do.")
        return

    summary_rows = []
    for run_id, vmem_path, raw_path in pairs:
        print(f"\n{run_id}:")
        vmem_csv = Path(INTERMEDIATE_DIR) / f"{run_id}_vmem_vadcount.csv"
        raw_csv = Path(INTERMEDIATE_DIR) / f"{run_id}_raw_vadcount.csv"

        try:
            print(f"  Running vadcount on {vmem_path.name}...")
            run_vadcount(vmem_path, vmem_csv)
            print(f"  Running vadcount on {raw_path.name}...")
            run_vadcount(raw_path, raw_csv)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            print(f"  [ERROR] Skipping {run_id}: {e}")
            continue

        try:
            rows = compare_pair(run_id, os_name, ram_tier, pressure, variant, vmem_csv, raw_csv)
        except ValueError as e:
            print(f"  [ERROR] Skipping {run_id}: {e}")
            continue

        detail_csv = Path(PER_RUN_DIR) / f"{run_id}_comparison.csv"
        write_detail_csv(rows, detail_csv)

        summary = summarize_run(run_id, os_name, ram_tier, pressure, variant, rows)
        summary_rows.append(summary)
        print(f"  Compared {summary['TotalProcesses']} processes -> "
              f"{summary['MatchCount']} match, {summary['SmallCount']} small, "
              f"{summary['MediumCount']} medium, {summary['LargeCount']} large, "
              f"{summary['ErrorCount']} error, {summary['MissingCount']} missing")
        print(f"  Detail written to {detail_csv}")

    if not summary_rows:
        print("\nNo runs summarized - nothing written.")
        return

    output_path = Path(OUTPUT_CSV)
    write_master_csv(summary_rows, output_path)

    print(f"\nDone. {len(summary_rows)} run(s) summarized to {output_path}")
    print(f"Full per-process detail for each run is in {PER_RUN_DIR}")


if __name__ == "__main__":
    main()
