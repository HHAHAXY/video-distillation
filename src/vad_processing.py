import argparse
import subprocess
import os
from pydub import AudioSegment
import matplotlib.pyplot as plt
import numpy as np
import tempfile
from silero_vad import load_silero_vad, read_audio, get_speech_timestamps

def convert_mp4_to_wav(video_path, output_wav_path=None):
    """convert mp4 video to wav audio"""
    dir_path = os.path.dirname(video_path)
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    output_wav_path = os.path.join(dir_path, f"{base_name}_temp.wav")
    command = f'ffmpeg -i "{video_path}" -ab 160k -ac 1 -ar 16000 -vn "{output_wav_path}" -y'
    subprocess.run(command, shell=True, check=True)
    
    return output_wav_path

def plot_segment_energy(wav_path, merged_segments):
    """calculate and plot mean audio energy for each segment"""
    
    print("loading audio for energy analysis...")
    audio = AudioSegment.from_file(wav_path)
    
    segment_energies = []
    segment_times = []
    segments_with_energy = []
    
    for segment in merged_segments:
        start_ms = segment['start'] * 1000
        end_ms = segment['end'] * 1000
        segment_audio = audio[start_ms:end_ms]
        
        samples = np.array(segment_audio.get_array_of_samples())
        rms = np.sqrt(np.mean(np.square(samples.astype(np.float64))))
        
        segments_with_energy.append({**segment, 'energy': rms})
        segment_energies.append(rms)
        segment_times.append((segment['start'] + segment['end']) / 2)
    
    mean_energy = np.mean(segment_energies)
    high_energy_segments = [s for s in segments_with_energy if s['energy'] > mean_energy]
    clean_segments = [{k: v for k, v in s.items() if k != 'energy'} for s in high_energy_segments]
    
    plt.figure(figsize=(15, 8))
    plt.plot(segment_times, segment_energies, 'b-', marker='o', label='segment energy')
    plt.axhline(y=mean_energy, color='r', linestyle='--', label=f'mean energy: {mean_energy:.2f}')
    plt.xlabel('time (seconds)')
    plt.ylabel('rms energy')
    plt.title('audio energy profile')
    plt.legend()
    plt.grid(True)
    
    
    return clean_segments, plt

def trim_video_by_speech(video_path, output_path, threshold=1.5):
    """trim video to keep only speech segments"""
    wav_path = convert_mp4_to_wav(video_path)
    
    wav = read_audio(wav_path)
    model = load_silero_vad()
    
    speech_timestamps = get_speech_timestamps(
        wav,
        model,
        return_seconds=True
    )
    
    merged_segments = []
    for seg in speech_timestamps:
        if merged_segments and seg['start'] - merged_segments[-1]['end'] < threshold:
            merged_segments[-1]['end'] = seg['end']
        else:
            merged_segments.append(seg)
    
    dir_path = os.path.dirname(video_path)
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    output_energy_plot_path = os.path.join(dir_path, f"{base_name}_energy_plot.png")

    clean_segments, plot = plot_segment_energy(wav_path, merged_segments)
    print(f"saving energy profile to: {output_energy_plot_path}")
    plot.savefig(output_energy_plot_path)
    plot.close()

    select_filter = "+".join([f"between(t,{s['start']},{s['end']})" for s in clean_segments])
    command = (
        f'ffmpeg -i "{video_path}" '
        f'-vf "select=\\'{select_filter}\\',setpts=N/FRAME_RATE/TB" '
        f'-af "aselect=\\'{select_filter}\\',asetpts=N/SR/TB" '
        f'"{output_path}" -y'
    )
    
    print("running ffmpeg to trim video...")
    subprocess.run(command, shell=True, check=True)
    
    if os.path.exists(wav_path):
        os.remove(wav_path)
        print(f"removed temporary wav file: {wav_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trim video to keep only speech segments")
    parser.add_argument("--input", required=True, help="Input video file path")
    parser.add_argument("--output", required=True, help="Output video file path")
    parser.add_argument("--threshold", type=float, default=1.5, 
                        help="Maximum gap in seconds between speech segments to merge them (default: 1.5)")
    
    args = parser.parse_args()
    
    print(f"processing: {args.input}")
    print(f"merge threshold: {args.threshold} seconds")
    
    try:
        trim_video_by_speech(args.input, args.output, args.threshold)
        print(f"successfully created trimmed video: {args.output}")
    except Exception as e:
        print(f"error processing video: {e}")