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
                         help="Seconds between the true (log-confirmed) unstun/checkpoint-complete "
                              "event and acquisition start. -1 means it couldn't be computed for this run.")
    parser.add_argument("--configured-delay", type=float, default=None,
                         help="The fixed delay (seconds) the pipeline was configured to wait before "
                              "firing WinPmem for this run -- log alongside --true-gap to see how "
                              "well-calibrated the delay was, and to compare across RAM tiers.")
    parser.add_argument("--checkpoint-total", type=float, default=None,
                         help="Seconds the true VMware checkpoint (stun to fully complete) took for "
                              "this run, per vmware.log's own CheckpointTiming line. -1 if not found. "
                              "Informational -- builds the cross-tier calibration dataset for the delay.")
    parser.add_argument("--measured-checkpoint-duration", type=float, default=None,
                         help="Seconds from this run's own snapshot-trigger timestamp to the real "
                              "unstun timestamp found in vmware.log -- an independent cross-check "
                              "against --checkpoint-total, and the number that actually tells you how "
                              "long --configured-delay should have been for this run. -1 if not found.")
    parser.add_argument("--memory-usage", type=float, default=None,
                         help="Optional: total memory usage (%%) if you have it")
    args = parser.parse_args()

    # Only taking what's necessary
    values = {
        "Snapshot Duration": args.snapshot_duration,
        "Acquisition delay time": args.configured_delay,
        "Time lapse between Snapshot unstun and Acquisition start": args.true_gap,
    }
    if args.memory_usage is not None:
        values["Total Memory usage"] = args.memory_usage

    write_run_data(args.xlsx, args.config, args.run, values)


if __name__ == "__main__":
    main()
