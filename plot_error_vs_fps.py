#!/usr/bin/env python3
import os
import glob
import pandas as pd
import matplotlib.pyplot as plt

def parse_ate(file_path):
    """Extracts RMSE (first value) from ate_evaluation.txt."""
    try:
        with open(file_path, 'r') as f:
            line = f.readline().strip()
            if line and "Warning" not in line:
                parts = line.split(',')
                if len(parts) >= 3:
                    return float(parts[0])  # Scaled RMSE is the first value
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return None

def main():
    results = []
    
    # Scan current directory for result folders matching pattern
    # Pattern: *_result_stereo_inertial_normal_*_fps_*_run_*
    for folder in glob.glob("*_result_stereo_inertial_normal_*_fps_*_run_*"):
        if not os.path.isdir(folder):
            continue
            
        # Example folder name: 2026-05-06_17-24-03_result_stereo_inertial_normal_MH01_0_fps_20_run_1
        parts = folder.split('_')
        
        # We need to extract Dataset and FPS from the folder name
        try:
            # Assuming 'normal' is parts[5], then dataset is parts[6]
            normal_idx = parts.index('normal')
            dataset = parts[normal_idx + 1]
            fps_idx = parts.index('fps')
            fps = int(parts[fps_idx + 1])
        except ValueError:
            print(f"Could not parse metadata from folder name: {folder}")
            continue
            
        ate_file = os.path.join(folder, 'ate_evaluation.txt')
        if os.path.exists(ate_file):
            rmse = parse_ate(ate_file)
            if rmse is not None:
                results.append({'Dataset': dataset, 'FPS': fps, 'ATE_RMSE': rmse})

    if not results:
        print("No valid ATE results found.")
        return

    df = pd.DataFrame(results)
    
    # Calculate average, min, and max ATE across all datasets for each FPS
    avg_df = df.groupby('FPS')['ATE_RMSE'].agg(['mean', 'min', 'max']).reset_index()
    avg_df = avg_df.sort_values(by='FPS')

    print("\nSummary of Average, Min, and Max ATE vs. Target FPS:")
    print(avg_df.to_string(index=False))

    # Plot
    plt.figure(figsize=(8, 6))
    
    # Plot the shaded region for min and max
    plt.fill_between(avg_df['FPS'], avg_df['min'], avg_df['max'], color='b', alpha=0.2, label='Min/Max Range')
    
    # Plot the average line
    plt.plot(avg_df['FPS'], avg_df['mean'], marker='o', linestyle='-', color='b', linewidth=2, markersize=8, label='Average ATE')
    
    # Optional: Scatter individual dataset points lightly in the background
    for dataset in df['Dataset'].unique():
        ds_data = df[df['Dataset'] == dataset].sort_values(by='FPS')
        plt.plot(ds_data['FPS'], ds_data['ATE_RMSE'], marker='x', linestyle='--', alpha=0.3)

    plt.title('Absolute Trajectory Error (ATE) vs. Target FPS', fontsize=14)
    plt.xlabel('Target FPS', fontsize=12)
    plt.ylabel('Average ATE RMSE [m]', fontsize=12)
    plt.xticks(avg_df['FPS'].unique())
    plt.grid(True, linestyle='--', alpha=0.7)
    
    # Legend for datasets
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
    plt.tight_layout()

    out_file = 'average_error_vs_fps.png'
    plt.savefig(out_file, dpi=300)
    print(f"\nSaved plot to {out_file}")

if __name__ == '__main__':
    main()
