# Ridgeline Weather Network — Data Quality Checker

**Harshita Gupta**  
[harshitawork208@gmail.com](mailto:harshitawork208@gmail.com)

**Video:** [Add your 3-minute screen recording link]  
**Run:** `python checker.py path/to/ridgeline_data_pack (2)`

## Overview

This project checks six weeks of weather observations from eight stations and generates `flags.csv` to help decide which data is suitable for the spring climate summary and which station needs technician attention.

## Checks

1. **Stuck humidity:** Flags long runs of identical, non-missing relative humidity readings (144 consecutive readings).
2. **Pressure sanity:** Compares mean station pressure with an elevation-based estimate and flags deviations greater than 50 hPa.
3. **Data gaps:** Flags intervals between consecutive observations that exceed 20 minutes.
4. **Duplicate timestamps:** Identifies stations with duplicate observation timestamps for review.
5. **GPS NMEA validation:** Checks supported NMEA sentences for invalid checksums and identifies void GPS fixes.

Flags indicate potential issues and should be interpreted alongside the observations and maintenance notes. A flag does not automatically mean that every measurement from that station is unusable.

## Requirements

- Python 3
- pandas

Install the dependency:

```bash
pip install pandas
```

## Running the checker

Run the command from the repository directory, replacing the example path with the location of the data pack:

```bash
python checker.py "path/to/data_pack"
```

The input data pack should follow the expected directory and file structure. The checker writes `flags.csv` to the current working directory, not into the data pack.

## Output: `flags.csv`

The output contains one row per detected issue, with these columns:

- `station_id` — station associated with the issue.
- `channel` — affected measurement channel or data category.
- `start_utc`, `end_utc` — flagged interval in UTC.
- `issue` — brief description of the issue.
- `action` — suggested handling of the flagged data.
- `note` — supporting evidence or context.

The output is intended to support review and documented decisions. Original observations should be preserved, and any exclusions or corrections should be recorded.

## What I did not get to

The checker uses rule-based thresholds and sanity checks. It does not independently establish the physical cause of every anomaly, calibrate sensors, or automatically resolve conflicting duplicate observations. These cases need further evidence or human review.

## Repository contents

- `checker.py` — data-quality checking script.
- `flags.csv` — generated flags for the assignment data pack.
- `report.pdf` — network health report answering the coordinator's two questions.
- `DECISIONS.md` — reasoning behind key decisions and uncertainties.
- `ai_logs/` — complete exports of AI-assisted work.

The original data pack is intentionally not included in this repository.