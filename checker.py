import os
import sys
import pandas as pd

def main():
    # sys.argv[0] is script name, the other is data folder path by user..
    if len(sys.argv) < 2:
        print("Usage: python checker.py <path_to_data_pack_folder>")
        sys.exit(1)

    data_dir = sys.argv[1]

    # Paths
    stations_path = os.path.join(data_dir, 'stations.csv')
    data_folder = os.path.join(data_dir, 'data')
    if not os.path.exists(data_folder):
        # if the user passed the data folder directly instead of root pack
        data_folder = data_dir
        stations_path = os.path.join(os.path.dirname(data_dir), 'stations.csv')

    flags = []

    #load station's metadata
    stations_df = None
    if os.path.exists(stations_path):
        stations_df = pd.read_csv(stations_path).set_index('station_id')

    #Looping Through Station CSV Files
    if os.path.exists(data_folder):
        for filename in os.listdir(data_folder):
            if filename.endswith('.csv') and filename.startswith('S'):
                station_id = filename.split('.')[0]
                file_path = os.path.join(data_folder, filename)
                
                df = pd.read_csv(file_path)
                df['timestamp_utc'] = pd.to_datetime(df['timestamp_utc'])

                 
                # Check 1: Stuck humidity (e.g. 100% for an extended period, like S05 in maintenance log)
                if 'rh_pct' in df.columns:
                    # Look for consecutive identical values lasting > 12 hours (72 intervals of 10 mins)
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
                    # Rough expected station pressure formula based on elevation
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

    # Write flags.csv to the current working directory
    flags_df = pd.DataFrame(flags)
    output_csv = 'flags.csv'
    flags_df.to_csv(output_csv, index=False)
    print(f"Successfully generated {output_csv} with {len(flags_df)} flags.")

if __name__ == '__main__':
    main()