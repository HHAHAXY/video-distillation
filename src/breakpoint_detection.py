import cv2
import argparse
import numpy as np
import subprocess
import os
import re
import easyocr
from tqdm import tqdm
from datetime import datetime
import matplotlib.pyplot as plt
from collections import Counter

def process_string(binary_image, reader):
    try:
        results = reader.readtext(binary_image)
        print(results)
        s = results[0][1]
        s = s.replace(" ", "")
        if re.fullmatch(r"\d+[\/|]\d+[\/|]\d+", s):
            return tuple(map(int, re.split(r'[/|]', s)))
        return None
    except Exception:
        return None

def detect_counter_breakpoints(
    video_path, 
    roi=(100, 65, 60, 20), 
    fps=60, 
    template_duration=5, 
    window_size=6, 
    consensus_threshold=0.75,
    output_dir="breakpoints",
    reader=None
):
    """
    detect counter breakpoints in a video using ocr
    """
    if reader is None:
        raise ValueError("ocr reader instance is required")
    
    os.makedirs(output_dir, exist_ok=True)
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"could not open video: {video_path}")
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0:
        fps = video_fps
    
    x, y, w, h = roi
    
    frames_per_chunk = fps
    sample_rate = int(fps / window_size)
    
    window_buffer = []
    breakpoints = []
    second_count = 0
    frame_count = 0
    current_counter_value = None
    
    total_seconds = total_frames // fps
    
    print("detecting breakpoints...")
    for second_count in tqdm(range(total_seconds), desc="analyzing video"):
        chunk_frames = []
        for _ in range(frames_per_chunk):
            ret, frame = cap.read()
            if not ret:
                break
            chunk_frames.append(frame)
            frame_count += 1
        
        if not chunk_frames:
            break
        
        sampled_frames = chunk_frames[::sample_rate]
        
        for frame in sampled_frames:
            cropped = frame[y:y+h, x:x+w]
            gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, None, fx=7, fy=7, interpolation=cv2.INTER_CUBIC)
            blurred = cv2.GaussianBlur(gray, (7, 7), 0)
            
            _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            counts = process_string(binary, reader)
            window_buffer.append(counts)
            if len(window_buffer) > window_size:
                window_buffer.pop(0)
            
            if len(window_buffer) == window_size:
                valid_counts = [s for s in window_buffer if s is not None]
                
                if len(valid_counts) > 0:
                    most_common = Counter(valid_counts).most_common(1)[0]
                    consensus_tuple, count = most_common
                    
                    if count / len(window_buffer) >= consensus_threshold:
                        if consensus_tuple != current_counter_value:
                            if is_counter_increased(current_counter_value, consensus_tuple):
                                print(f"breakpoint detected at second {second_count} - counter changed from {current_counter_value} to {consensus_tuple}")
                                
                                breakpoints.append((second_count, frame_count / fps))
                                
                                current_counter_value = consensus_tuple
    
    cap.release()
    
    print("extracting clips around breakpoints...")
    clips = []
    
    for i, (second, exact_time) in enumerate(breakpoints):
        start_time = max(0, exact_time - template_duration)
        end_time = max(0, exact_time + template_duration)
        
        output_file = os.path.join(output_dir, f"breakpoint_{i}_{second}s.mp4")
        clips.append(output_file)
        
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_time),
            "-to", str(end_time),
            "-c:v", "libx264",
            "-c:a", "aac",
            output_file
        ]
        
        print(f"extracting clip {i+1}/{len(breakpoints)}...")
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    if clips:
        print("merging clips...")
        list_file = os.path.join(output_dir, "clips_list.txt")
        with open(list_file, "w") as f:
            for clip in clips:
                f.write(f"file '{clip}'\n")
        
        merged_output = os.path.join(output_dir, "breakpoints_merged.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            merged_output
        ]
        
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"merged clip saved to: {merged_output}")
    
    return breakpoints

def is_counter_increased(prev_value, current_value):
    """
    compare two counter values to see if any number has increased
    """
    if prev_value is None:
        return True
    
    return any(c > p for p, c in zip(prev_value, current_value))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Detect counter changes in video using OCR")
    parser.add_argument("--input", required=True, type=str, help="Input video file path")
    args = parser.parse_args()
    
    reader = easyocr.Reader(['en'])
    print(f"processing: {args.input}")
    try:
        breakpoints = detect_counter_breakpoints(args.input, reader=reader)
        print(f"successfully created trimmed video.")
    except Exception as e:
        print(f"error processing video: {e}")
