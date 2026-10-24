
import os
import sys
import pandas as pd


def validate_nmea_checksum(sentence):
    """Validate an NMEA sentence using its checksum."""
    if not isinstance(sentence, str) or not sentence.startswith('$'):
        return False

    try:
        body, checksum_str = sentence.strip().rsplit('*', 1)
        expected_checksum = int(checksum_str, 16)

        calc_checksum = 0
        for char in body[1:]:
            calc_checksum ^= ord(char)

        return calc_checksum == expected_checksum
    except (ValueError, TypeError):
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python checker.py <path_to_data_pack_folder>")
        sys.exit(1)

    data_dir = sys.argv[1]

    # Paths
    stations_path = os.path.join(data_dir, 'stations.csv')
    data_folder = os.path.join(data_dir, 'data')
    gps_folder = os.path.join(data_dir, 'gps')

    # Support passing the data folder directly
    if not os.path.exists(data_folder) and not os.path.exists(gps_folder):
        data_dir_parent = os.path.dirname(data_dir)
        stations_path = os.path.join(data_dir_parent, 'stations.csv')
        data_folder = data_dir
        gps_folder = os.path.join(data_dir_parent, 'gps')

    flags = []

    # Load station metadata
    stations_df = None
    if os.path.exists(stations_path):
        stations_df = pd.read_csv(stations_path).set_index('station_id')

    # 1. Check station CSV files
    if os.path.exists(data_folder):
        for filename in os.listdir(data_folder):
            if not (filename.endswith('.csv') and filename.startswith('S')):
                continue

            station_id = filename.split('.')[0]
            file_path = os.path.join(data_folder, filename)

            df = pd.read_csv(file_path)
            df['timestamp_utc'] = pd.to_datetime(
                df['timestamp_utc'], errors='coerce'
            )
            df = df.dropna(subset=['timestamp_utc'])
            df = df.sort_values('timestamp_utc').reset_index(drop=True)

            # Check 1: Stuck humidity
            if 'rh_pct' in df.columns:
                run_id = (
                    df['rh_pct'].ne(df['rh_pct'].shift()).cumsum()
                )

                for _, run in df.groupby(run_id):
                    if (
                        len(run) >= 144
                        and run['rh_pct'].nunique(dropna=False) == 1
                        and pd.notna(run['rh_pct'].iloc[0])
                    ):
                        flags.append({
                            'station_id': station_id,
                            'channel': 'rh_pct',
                            'start_utc': run['timestamp_utc'].iloc[0].strftime(
                                '%Y-%m-%d %H:%M'
                            ),
                            'end_utc': run['timestamp_utc'].iloc[-1].strftime(
                                '%Y-%m-%d %H:%M'
                            ),
                            'issue': 'Humidity stuck at constant value',
                            'action': 'exclude',
                            'note': (
                                f"Humidity remained at "
                                f"{run['rh_pct'].iloc[0]} for "
                                f"{len(run)} consecutive readings."
                            )
                        })

            # Check 2: Pressure sanity vs station elevation
            if (
                'pressure_hpa' in df.columns
                and stations_df is not None
                and station_id in stations_df.index
                and 'elevation_m' in stations_df.columns
            ):
                elev = stations_df.loc[station_id, 'elevation_m']

                if pd.notna(elev) and (1 - 2.255e-5 * elev) > 0:
                    expected_p = (
                        1013.25 * (1 - 2.255e-5 * elev) ** 5.255
                    )
                    mean_p = pd.to_numeric(
                        df['pressure_hpa'], errors='coerce'
                    ).mean()

                    if (
                        pd.notna(mean_p)
                        and abs(mean_p - expected_p) > 50
                    ):
                        flags.append({
                            'station_id': station_id,
                            'channel': 'pressure_hpa',
                            'start_utc': df['timestamp_utc'].min().strftime(
                                '%Y-%m-%d %H:%M'
                            ),
                            'end_utc': df['timestamp_utc'].max().strftime(
                                '%Y-%m-%d %H:%M'
                            ),
                            'issue': 'Abnormal station pressure baseline',
                            'action': 'correct',
                            'note': (
                                'Pressure baseline deviates from expected '
                                f'elevation pressure ({expected_p:.1f} hPa).'
                            )
                        })

            # Check 3: Missing data / gaps
            time_diffs = df['timestamp_utc'].diff()
            gaps = df.loc[
                time_diffs > pd.Timedelta(minutes=20)
            ]

            for idx, row in gaps.iterrows():
                prev_time = df.loc[idx - 1, 'timestamp_utc']
                curr_time = row['timestamp_utc']

                flags.append({
                    'station_id': station_id,
                    'channel': 'all',
                    'start_utc': prev_time.strftime('%Y-%m-%d %H:%M'),
                    'end_utc': curr_time.strftime('%Y-%m-%d %H:%M'),
                    'issue': 'Data gap exceeding 20 minutes',
                    'action': 'exclude',
                    'note': 'Logger offline or transmission failure.'
                })

            # Check 4: Duplicate timestamps
            duplicate_rows = df[
                df['timestamp_utc'].duplicated(keep=False)
            ]

            if not duplicate_rows.empty:
                duplicate_times = duplicate_rows['timestamp_utc']

                # One grouped flag per affected station
                flags.append({
                    'station_id': station_id,
                    'channel': 'all',
                    'start_utc': duplicate_times.min().strftime(
                        '%Y-%m-%d %H:%M'
                    ),
                    'end_utc': duplicate_times.max().strftime(
                        '%Y-%m-%d %H:%M'
                    ),
                    'issue': 'Duplicate timestamps',
                    'action': 'review',
                    'note': (
                        f'{duplicate_times.nunique()} distinct timestamps '
                        'have duplicate records; review duplicated observations.'
                    )
                })

    # 2. Check GPS NMEA files
    if os.path.exists(gps_folder):
        for filename in os.listdir(gps_folder):
            if not filename.endswith(('.nmea', '.txt', '.log', '.csv')):
                continue

            station_id = filename.split('.')[0]
            gps_path = os.path.join(gps_folder, filename)

            with open(
                gps_path, 'r', encoding='utf-8', errors='replace'
            ) as f:
                for line in f:
                    line = line.strip()

                    if not line:
                        continue

                    # Separate timestamp from the NMEA sentence
                    parts = line.split(',', 1)

                    if len(parts) == 2 and parts[1].lstrip().startswith('$'):
                        timestamp_str = parts[0].strip()
                        nmea_sentence = parts[1].strip()
                    else:
                        timestamp_str = 'Unknown'
                        nmea_sentence = line

                    if not (
                        nmea_sentence.startswith('$GPRMC')
                        or nmea_sentence.startswith('$GPGGA')
                    ):
                        continue

                    is_valid = validate_nmea_checksum(nmea_sentence)

                    # RMC fields: $GPRMC, time, status, ...
                    fields = nmea_sentence.split(',')
                    is_rmc = fields[0].startswith('$GPRMC')
                    is_void = (
                        is_rmc
                        and len(fields) > 2
                        and fields[2].strip() == 'V'
                    )

                    if not is_valid or is_void:
                        issue_desc = (
                            'Invalid NMEA checksum'
                            if not is_valid
                            else 'GPS fix void (Status V)'
                        )

                        flags.append({
                            'station_id': station_id,
                            'channel': 'gps_nmea',
                            'start_utc': timestamp_str,
                            'end_utc': timestamp_str,
                            'issue': issue_desc,
                            'action': 'exclude',
                            'note': (
                                'Corrupted or unverified NMEA packet: '
                                f'{nmea_sentence[:30]}...'
                            )
                        })

    # 3. Write flags.csv
    columns = [
        'station_id',
        'channel',
        'start_utc',
        'end_utc',
        'issue',
        'action',
        'note'
    ]

    flags_df = pd.DataFrame(flags, columns=columns)
    output_csv = 'flags.csv'
    flags_df.to_csv(output_csv, index=False)

    print(f"Successfully generated {output_csv} with {len(flags_df)} flags.")

    if not flags_df.empty:
        print("\nFlags by issue:")
        print(flags_df['issue'].value_counts().to_string())


if __name__ == '__main__':
    main()
