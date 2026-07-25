import argparse
import csv

PAGE_SIZE = 4096

#Gap in raw file that needs to be ignored
HOLE_START = 0xC0000000  # 3GB
HOLE_END = 0x100000000   # 4GB
HOLE_SIZE = HOLE_END - HOLE_START

#Adjust the raw file after 1Gb gap 
def translate_offset(raw_offset: int) -> int | None:
    if raw_offset < HOLE_START:
        return raw_offset
    if raw_offset < HOLE_END:
        return None
    return raw_offset - HOLE_SIZE

#Verify both files are the sizes they are meant to be before attempting a comparison
def check_file_sizes(raw_path: str, vmem_path: str) -> None:
    import os
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


def compare_pages(raw_path: str, vmem_path: str, out_csv: str) -> None:

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


def main():
    parser = argparse.ArgumentParser(
        description="Compare WinPmem .raw vs VMware .vmem for page smearing."
    )
    parser.add_argument("raw", help="Path to WinPmem .raw acquisition")
    parser.add_argument("vmem", help="Path to VMware .vmem snapshot")
    parser.add_argument("--out", default="smeared_pages.csv",
                         help="CSV output path for smeared page offsets")
    args = parser.parse_args()

    check_file_sizes(args.raw, args.vmem)
    compare_pages(args.raw, args.vmem, args.out)


if __name__ == "__main__":
    main()
