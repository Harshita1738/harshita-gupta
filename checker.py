import os
import sys
import pandas as pd

def validate_nmea_checksum(sentence):
    """Validates an NMEA sentence using its checksum."""
    if not isinstance(sentence, str) or not sentence.startswith('$'):
        return False
    try:
        body, checksum_str = sentence.strip().rsplit('*', 1)
        expected_checksum = int(checksum_str, 16)
        
        calc_checksum = 0
        for char in body[1:]:
            calc_checksum ^= ord(char)
            
        return calc_checksum == expected_checksum
    except Exception:
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

    if not os.path.exists(data_folder) and not os.path.exists(gps_folder):
        # if the user passed the data folder directly instead of root pack
        data_dir_parent = os.path.dirname(data_dir)
        stations_path = os.path.join(data_dir_parent, 'stations.csv')
        data_folder = data_dir
        gps_folder = os.path.join(data_dir_parent, 'gps')

    flags = []

    # Load station's metadata
    stations_df = None
    if os.path.exists(stations_path):
        stations_df = pd.read_csv(stations_path).set_index('station_id')

    # 1. Looping Through Station CSV Files
    if os.path.exists(data_folder):
        for filename in os.listdir(data_folder):
            if filename.endswith('.csv') and filename.startswith('S'):
                station_id = filename.split('.')[0]
                file_path = os.path.join(data_folder, filename)
                
                df = pd.read_csv(file_path)
                df['timestamp_utc'] = pd.to_datetime(df['timestamp_utc'])
                 
                # Check 1: Stuck humidity
                if 'rh_pct' in df.columns:
                    stuck = (df['rh_pct'] == df['rh_pct'].shift()).rolling(window=72).sum()
                    stuck_indices = df.index[stuck >= 71]
                    if len(stuck_indices) > 0:
                        start_time = df.loc[stuck_indices[0] - 71, 'timestamp_utc'].strftime('%Y-%m-%d %H:%M')
                        end_time = df.loc[stuck_indices[-1], 'timestamp_utc'].strftime('%Y-%m-%d %H:%M')
                        flags.append({
                            'station_id': station_id,
                            'channel': 'rh_pct',
                            'start_utc': start_time,
                            'end_utc': end_time,
                            'issue': 'Humidity stuck at constant value',
                            'action': 'exclude',
                            'note': 'Sensor flatlined, matching field report of stuck humidity.'
                        })

                # Check 2: Pressure sanity vs station elevation
                if 'pressure_hpa' in df.columns and stations_df is not None and station_id in stations_df.index:
                    elev = stations_df.loc[station_id, 'elevation_m']
                    expected_p = 1013.25 * (1 - 22.55e-5 * elev)**5.255
                    mean_p = df['pressure_hpa'].mean()
                    if abs(mean_p - expected_p) > 50:
                        flags.append({
                            'station_id': station_id,
                            'channel': 'pressure_hpa',
                            'start_utc': df['timestamp_utc'].min().strftime('%Y-%m-%d %H:%M'),
                            'end_utc': df['timestamp_utc'].max().strftime('%Y-%m-%d %H:%M'),
                            'issue': 'Abnormal station pressure baseline',
                            'action': 'correct',
                            'note': f'Pressure baseline deviates from expected elevation pressure ({expected_p:.1f} hPa).'
                        })

                # Check 3: Missing data / gaps
                df = df.sort_values('timestamp_utc')
                time_diffs = df['timestamp_utc'].diff()
                gaps = df[time_diffs > pd.Timedelta(minutes=20)]
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

    # 2. Looping Through GPS Log Files
    if os.path.exists(gps_folder):
        for filename in os.listdir(gps_folder):
            if filename.endswith(('.txt', '.log', '.csv')):
                station_id = filename.split('.')[0]
                gps_path = os.path.join(gps_folder, filename)
                
                with open(gps_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        # Example line format: 2025-03-01 00:00:00,$GPRMC,...
                        parts_comma = line.split(',')
                        timestamp_str = parts_comma[0] if len(parts_comma) > 0 else 'Unknown'
                        
                        # Extract the NMEA sentence part
                        nmea_sentence = ','.join(parts_comma[1:]) if ',' in line else line
                        
                        if '$GPRMC' in nmea_sentence or '$GPGGA' in nmea_sentence:
                            is_valid = validate_nmea_checksum(nmea_sentence)
                            is_void = '$GPRMC' in nmea_sentence and len(parts_comma) > 3 and parts_comma[3] == 'V'
                            
                            if not is_valid or is_void:
                                issue_desc = 'Invalid NMEA checksum' if not is_valid else 'GPS fix void (Status V)'
                                flags.append({
                                    'station_id': station_id,
                                    'channel': 'gps_nmea',
                                    'start_utc': timestamp_str,
                                    'end_utc': timestamp_str,
                                    'issue': issue_desc,
                                    'action': 'exclude',
                                    'note': f'Corrupted or unverified NMEA packet: {nmea_sentence[:30]}...'
                                })

    # Write flags.csv to the current working directory
    flags_df = pd.DataFrame(flags)
    output_csv = 'flags.csv'
    flags_df.to_csv(output_csv, index=False)
    print(f"Successfully generated {output_csv} with {len(flags_df)} flags.")

if __name__ == '__main__':
    main()