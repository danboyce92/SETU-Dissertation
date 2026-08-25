import argparse
from xlsx_writer import write_run_data

def main():
    parser = argparse.ArgumentParser(
        description="Write snapshot/acquisition timing into the tracking workbook."
    )
    parser.add_argument("--xlsx", required=True, help="Path to the tracking workbook")
    parser.add_argument("--config", required=True, help="Sheet name, e.g. Win10_8Gb_2")
    parser.add_argument("--run", required=True, type=int, help="Run number, e.g. 7")
    parser.add_argument("--snapshot-duration", required=True, type=float)
    parser.add_argument("--acquisition-duration", required=True, type=float)
    parser.add_argument("--gap", required=True, type=float,
                         help="Seconds between snapshot end (vmrun return) and acquisition start "
                              "-- kept for comparability with the legacy/blocking dataset, expected "
                              "to be ~0 under the async-trigger pipeline since it no longer gates anything")
    parser.add_argument("--true-gap", type=float, default=None,
                         help="Seconds between the true unstun/checkpoint-complete event and "
                              "acquisition start -- the real staleness gap under the async-trigger pipeline")
    parser.add_argument("--memory-usage", type=float, default=None,
                         help="Optional: total memory usage (%%) if you have it")
    args = parser.parse_args()

    values = {
        "Snapshot Duration": args.snapshot_duration,
        "Acquisition Duration": args.acquisition_duration,
        "Time lapse between Snapshot end and Acquisition start": args.gap,
    }
    if args.true_gap is not None:
        values["True Gap (unstun to acquisition start)"] = args.true_gap
    if args.memory_usage is not None:
        values["Total Memory usage"] = args.memory_usage

    write_run_data(args.xlsx, args.config, args.run, values)


if __name__ == "__main__":
    main()
