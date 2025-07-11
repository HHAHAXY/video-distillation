#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import argparse
import requests
import time
from pydub import AudioSegment

API_KEY = os.environ.get("ACOUSTID_API_KEY")
if not API_KEY:
    raise ValueError("AcoustID API key not found. Please set the ACOUSTID_API_KEY environment variable.")
SEGMENT_LENGTH = 15
ACOUSTID_API_URL = "https://api.acoustid.org/v2/lookup"

def extract_audio(video_path, output_path="extracted_audio.wav"):
    """extract audio from video using ffmpeg"""
    cmd = [
        "ffmpeg", "-i", video_path, 
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "44100",
        "-ac", "2",
        "-y",
        output_path
    ]
    
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"audio extracted to {output_path}")
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"error extracting audio: {e}")
        sys.exit(1)

def split_audio(audio_path, segment_length=SEGMENT_LENGTH):
    """split audio into segments"""
    print(f"loading audio file {audio_path}...")
    audio = AudioSegment.from_file(audio_path)
    total_duration = len(audio) / 1000
    
    segments = []
    for start_time in range(0, int(total_duration), segment_length):
        end_time = min(start_time + segment_length, total_duration)
        
        start_ms = start_time * 1000
        end_ms = end_time * 1000
        
        segment_audio = audio[start_ms:end_ms]
        segment_file = f"segment_{start_time}_{end_time}.wav"
        segment_audio.export(segment_file, format="wav")
        
        segments.append({
            "file": segment_file,
            "start_time": start_time,
            "end_time": end_time
        })
    
    print(f"audio split into {len(segments)} segments")
    return segments

def generate_fingerprint(audio_file):
    """generate chromaprint fingerprint using fpcalc"""
    cmd = [
        "fpcalc",
        "-json",
        "-length", str(SEGMENT_LENGTH),
        audio_file
    ]
    
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        fingerprint_data = json.loads(result.stdout.decode('utf-8'))
        return fingerprint_data
    except subprocess.CalledProcessError as e:
        print(f"error generating fingerprint: {e}")
        print(f"make sure 'fpcalc' is installed (chromaprint)")
        sys.exit(1)
    except json.JSONDecodeError:
        print("failed to parse fpcalc output")
        sys.exit(1)

def lookup_fingerprint(fingerprint, duration):
    """lookup fingerprint using acoustid api"""
    params = {
        'client': API_KEY,
        'duration': int(duration),
        'fingerprint': fingerprint,
        'format': 'json'
    }
    try:
        response = requests.get(ACOUSTID_API_URL, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"api request failed: {e}")
        return {"status": "error", "error": str(e)}

def process_segment(segment):
    """process a single audio segment for copyright"""
    print(f"processing segment: {format_time(segment['start_time'])} - {format_time(segment['end_time'])}")
    
    fingerprint_data = generate_fingerprint(segment["file"])
    
    if 'fingerprint' in fingerprint_data and 'duration' in fingerprint_data:
        result = lookup_fingerprint(fingerprint_data['fingerprint'], fingerprint_data['duration'])
        print(result)
        segment["results"] = result
        segment["has_match"] = False
        
        if result.get("status") == "ok" and "results" in result:
            segment["has_match"] = len(result["results"]) > 0
        
        os.remove(segment["file"])
        
        time.sleep(1)
        
        return segment
    else:
        print(f"failed to generate fingerprint for {segment['file']}")
        segment["error"] = "failed to generate fingerprint"
        return segment

def format_time(seconds):
    """format seconds to hh:mm:ss"""
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"

def extract_recording_info(result):
    """extract recording info from acoustid result"""
    recordings = []
    
    if "results" in result:
        for match in result["results"]:
            if "recordings" in match:
                for recording in match["recordings"]:
                    recording_info = {
                        "title": recording.get("title", "Unknown"),
                        "artists": []
                    }
                    
                    if "artists" in recording:
                        for artist in recording["artists"]:
                            recording_info["artists"].append(artist.get("name", "Unknown Artist"))
                    
                    recordings.append(recording_info)
    
    return recordings

def process_video(video_path):
    """main function to process video for copyright"""
    print(f"processing video: {video_path}")
    
    audio_path = extract_audio(video_path)
    
    segments = split_audio(audio_path)
    
    copyright_segments = []
    total_segments = len(segments)
    
    print(f"beginning fingerprinting of {total_segments} segments...")
    for i, segment in enumerate(segments):
        print(f"processing segment {i+1}/{total_segments}")
        processed_segment = process_segment(segment)
        
        if processed_segment.get("has_match", False):
            copyright_segments.append(processed_segment)
            
            print(f"⚠️ potential copyright music detected at {format_time(segment['start_time'])} - {format_time(segment['end_time'])}")
            recordings = extract_recording_info(processed_segment["results"])
            
            for recording in recordings:
                artists = ", ".join(recording["artists"])
                print(f"   - {recording['title']} by {artists}")
    
    os.remove(audio_path)
    
    print("
=== copyright music detection report ===")
    if not copyright_segments:
        print("no copyright music detected.")
    else:
        print(f"detected {len(copyright_segments)} segments with potential copyright music:")
        for segment in copyright_segments:
            print(f"• {format_time(segment['start_time'])} - {format_time(segment['end_time'])}")
            recordings = extract_recording_info(segment["results"])
            
            for recording in recordings:
                artists = ", ".join(recording["artists"])
                print(f"   - {recording['title']} by {artists}")
    
    with open("copyright_detection_results.json", "w") as f:
        json.dump(copyright_segments, f, indent=2)
    
    print(f"
detailed results saved to copyright_detection_results.json")

def check_dependencies():
    """check for required dependencies"""
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("error: ffmpeg is not installed or not in path")
        print("please install ffmpeg: https://ffmpeg.org/download.html")
        sys.exit(1)
    
    try:
        subprocess.run(["fpcalc", "-version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("error: fpcalc (chromaprint) is not installed or not in path")
        print("please install chromaprint: https://acoustid.org/chromaprint")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Detect copyright music in video files using AcoustID")
    parser.add_argument("video", help="Path to video file")
    args = parser.parse_args()
    
    check_dependencies()
    
    process_video(args.video)