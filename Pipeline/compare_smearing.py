import argparse
import csv
import os

PAGE_SIZE = 4096

# Fixed folder where every comparison's CSV output gets written
OUTPUT_DIR = r"E:\Research\SharedFolder\Acquisitions"

# Gap in raw file that needs to be ignored
# 3GB - 4GB
HOLE_START = 0xC0000000  
HOLE_END = 0x100000000   
HOLE_SIZE = HOLE_END - HOLE_START

# Adjust the raw file after 1Gb gap 
def translate_offset(raw_offset: int) -> int | None:
    if raw_offset < HOLE_START:
        return raw_offset
    if raw_offset < HOLE_END:
        return None
    return raw_offset - HOLE_SIZE

# Verify both files are the sizes they are meant to be before attempting a comparison
def check_file_sizes(raw_path: str, vmem_path: str) -> None:
    raw_size = os.path.getsize(raw_path)
    vmem_size = os.path.getsize(vmem_path)

    print(f"raw:  {raw_path} ({raw_size} bytes)")
    print(f"vmem: {vmem_path} ({vmem_size} bytes)")

    if raw_size - vmem_size != HOLE_SIZE:
        print(f"\nERROR: expected raw size to exceed vmem size by exactly "
              f"{HOLE_SIZE} bytes (the padded hole), but the difference is "
              f"{raw_size - vmem_size} bytes. These files probably aren't "
              f"a matching pair -- aborting.")
        raise SystemExit(1)


def compare_pages(raw_path: str, vmem_path: str, out_csv: str) -> dict:

    matches = 0
    smeared = 0
    excluded = 0
    smeared_pages = []

    with open(raw_path, "rb") as f_raw, open(vmem_path, "rb") as f_vmem:
        f_raw.seek(0, 2)
        raw_size = f_raw.tell()
        f_raw.seek(0)

        offset = 0
        while offset < raw_size:
            vmem_offset = translate_offset(offset)

            if vmem_offset is None:
                excluded += 1
                offset += PAGE_SIZE
                continue

            f_raw.seek(offset)
            raw_page = f_raw.read(PAGE_SIZE)

            f_vmem.seek(vmem_offset)
            vmem_page = f_vmem.read(PAGE_SIZE)

            if len(raw_page) < PAGE_SIZE or len(vmem_page) < PAGE_SIZE:
                # ran off the end of one file -- stop comparing
                break

            if raw_page == vmem_page:
                matches += 1
            else:
                smeared += 1
                smeared_pages.append((hex(vmem_offset), hex(offset)))

            offset += PAGE_SIZE

    total = matches + smeared + excluded

    #Print to CLI
    print("\n--- Comparison summary ---")
    print(f"Total pages considered: {total}")
    if total:
        print(f"  Match:    {matches} ({matches/total*100:.2f}%)")
        print(f"  Smeared:  {smeared} ({smeared/total*100:.2f}%)")
        print(f"  Excluded: {excluded} ({excluded/total*100:.2f}%)")

    with open(out_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["vmem_offset", "raw_offset"])
        writer.writerows(smeared_pages)
    print(f"\nSmeared page offsets written to {out_csv} "
          f"({len(smeared_pages)} rows) for VAD triangulation.")

    return {
        "Total pages": total,
        "Matched Count": matches,
        "Smeared Count": smeared,
        "Total excluded": excluded,
        "Smeared Percentage": round(smeared / total * 100, 2) if total else None,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Compare WinPmem .raw vs VMware .vmem for page smearing."
    )
    parser.add_argument("raw", help="Path to WinPmem .raw acquisition")
    parser.add_argument("vmem", help="Path to VMware .vmem snapshot")
    parser.add_argument("csv_name", nargs="?", default="smeared_pages.csv",
                         help="Filename for the CSV output (saved into "
                              f"{OUTPUT_DIR}). Defaults to smeared_pages.csv")
    parser.add_argument("--xlsx", help="Path to the tracking workbook, if you "
                         "want results written straight into it")
    parser.add_argument("--config", help="Sheet name (config) to write into, "
                         "e.g. Win10_8Gb_2. Required if --xlsx is given.")
    parser.add_argument("--run", type=int, help="Run number to write into, "
                         "e.g. 7. Required if --xlsx is given.")
    args = parser.parse_args()

    out_csv = os.path.join(OUTPUT_DIR, args.csv_name)

    check_file_sizes(args.raw, args.vmem)
    stats = compare_pages(args.raw, args.vmem, out_csv)

    if args.xlsx:
        if not args.config or args.run is None:
            print("\nERROR: --config and --run are both required when --xlsx is given.")
            return
        from xlsx_writer import write_run_data
        write_run_data(args.xlsx, args.config, args.run, stats)


if __name__ == "__main__":
    main()
