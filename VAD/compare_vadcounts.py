
# python compare_vadcounts.py vmem_vadcount.csv raw_vadcount.csv results.csv

import csv
import sys


def load_counts(path):
    # Load PID -> row dict from a vadcount.py CSV output.

    for encoding in ("utf-8-sig", "utf-16"):
        try:
            with open(path, encoding=encoding) as f:
                rows = list(csv.DictReader(f))
            if rows and "PID" in rows[0]:
                return {int(row["PID"]): row for row in rows}
        except (UnicodeError, UnicodeDecodeError):
            continue
    raise ValueError(f"Could not read {path} as UTF-8 or UTF-16 CSV")


def tier_for_delta(abs_delta):
    """Bucket an absolute delta into a severity tier."""
    if abs_delta == 0:
        return "MATCH"
    if abs_delta <= 5:
        return "SMALL"
    if abs_delta <= 20:
        return "MEDIUM"
    return "LARGE"


def main(vmem_path, raw_path, output_path):
    vmem_counts = load_counts(vmem_path)
    raw_counts = load_counts(raw_path)

    all_pids = sorted(set(vmem_counts) | set(raw_counts))

    results = []
    tier_totals = {"MATCH": 0, "SMALL": 0, "MEDIUM": 0, "LARGE": 0}
    missing = 0

    for pid in all_pids:
        vmem_row = vmem_counts.get(pid)
        raw_row = raw_counts.get(pid)

        if vmem_row is None or raw_row is None:
            missing += 1
            name = (vmem_row or raw_row)["Process"]
            status = "MISSING FROM VMEM" if vmem_row is None else "MISSING FROM RAW"
            results.append(
                {
                    "PID": pid,
                    "Process": name,
                    "VmemCount": "",
                    "RawCount": "",
                    "Delta": "",
                    "Status": status,
                    "Tier": "MISSING",
                }
            )
            continue

        vmem_count = int(vmem_row["VadNodeCount"])
        raw_count = int(raw_row["VadNodeCount"])
        delta = raw_count - vmem_count
        tier = tier_for_delta(abs(delta))
        tier_totals[tier] += 1
        status = "MATCH" if delta == 0 else "MISMATCH"

        results.append(
            {
                "PID": pid,
                "Process": vmem_row["Process"],
                "VmemCount": vmem_count,
                "RawCount": raw_count,
                "Delta": delta,
                "Status": status,
                "Tier": tier,
            }
        )

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["PID", "Process", "VmemCount", "RawCount", "Delta", "Status", "Tier"]
        )
        writer.writeheader()
        writer.writerows(results)

    compared = len(all_pids) - missing
    print(f"Results written to {output_path}")
    print()
    print(f"Total processes compared: {compared}")
    print(f"Processes missing from one file: {missing}")
    print()
    print("Delta breakdown:")
    print(f"  Exact match:        {tier_totals['MATCH']}")
    print(f"  Small (1-5):        {tier_totals['SMALL']}")
    print(f"  Medium (6-20):      {tier_totals['MEDIUM']}")
    print(f"  Large (21+):        {tier_totals['LARGE']}")
    print()
    mismatches = tier_totals["SMALL"] + tier_totals["MEDIUM"] + tier_totals["LARGE"]
    if compared:
        print(f"Overall mismatch rate: {mismatches}/{compared} ({100 * mismatches / compared:.1f}%)")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python compare_vadcounts.py <vmem_csv> <raw_csv> <output_csv>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
