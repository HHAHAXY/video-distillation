import os
import cv2
import openai
import argparse
import numpy as np
from tqdm import tqdm
import speech_recognition as sr
from pydub import AudioSegment
from moviepy import VideoFileClip, concatenate_videoclips
from collections import namedtuple
import tempfile
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

Scene = namedtuple("Scene", ["start", "end"])

def calculate_audio_energy(audio_segment):
    """calculate rms energy of audio segment"""
    return audio_segment.rms

def calculate_scene_scores(scene, audio_energy, motion_activity, speech_detected, weights):
    """calculate combined score for each scene"""
    return (
        weights['audio'] * audio_energy +
        weights['motion'] * motion_activity +
        weights['speech'] * int(speech_detected)
    )

def find_scenes_opencv(video_path, diff_threshold=0.5, scene_detection_skip=5, min_scene_duration=5.0, motion_threshold=0.05):
    """
    enhanced scene detection with robustness filters
    """
    scenes = []
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logging.error(f"failed to open video: {video_path}")
            return scenes

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        current_scene_start = 0.0
        ret, prev_frame = cap.read()
        if not ret:
            logging.error("could not read the first frame.")
            cap.release()
            return scenes

        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        
        prev_hsv = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2HSV)
        prev_hist = cv2.calcHist([prev_hsv], [0, 1], None, [50, 50], [0, 180, 0, 256])
        cv2.normalize(prev_hist, prev_hist, 0, 1, cv2.NORM_MINMAX)

        significant_changes = 0
        max_insignificant_changes = 3

        with tqdm(total=total_frames, desc="Scene Detection", unit="frames") as pbar:
            while True:
                for _ in range(scene_detection_skip):
                    cap.grab()

                ret, frame = cap.read()
                if not ret:
                    break

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                flow = cv2.calcOpticalFlowFarneback(prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                magnitude, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                motion_intensity = np.mean(magnitude)

                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                hist = cv2.calcHist([hsv], [0, 1], None, [50, 50], [0, 180, 0, 256])
                cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)

                distance = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL)
                color_change_intensity = 1 - distance

                combined_change = (color_change_intensity * 0.7) + (motion_intensity * 0.3)

                if combined_change > diff_threshold and motion_intensity > motion_threshold:
                    significant_changes += 1
                    
                    if significant_changes > max_insignificant_changes:
                        current_time = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
                        
                        if (current_time - current_scene_start) >= min_scene_duration:
                            scenes.append(Scene(current_scene_start, current_time))
                            current_scene_start = current_time
                            significant_changes = 0
                else:
                    significant_changes = max(0, significant_changes - 1)

                prev_gray = gray
                prev_hist = hist

                pbar.update(scene_detection_skip + 1)

            final_time = total_frames / fps
            if (final_time - current_scene_start) >= min_scene_duration:
                scenes.append(Scene(current_scene_start, final_time))

        cap.release()
    except Exception as e:
        logging.error(f"[scene detection error]: {e}")
    return scenes

def extract_audio_features(video_path, scenes):
    """extract audio energy and detect speech for each scene using whisper api"""

    audio_data = []
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
    client = openai.OpenAI(api_key=api_key)

    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
            video = VideoFileClip(video_path)
            video.audio.write_audiofile(temp_audio.name, codec="pcm_s16le")
            video.close()

            audio = AudioSegment.from_file(temp_audio.name)
            for scene in scenes:
                segment = audio[int(scene.start * 1000):int(scene.end * 1000)]
                energy = calculate_audio_energy(segment)

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_segment:
                    segment.export(temp_segment.name, format="wav")

                    try:
                        with open(temp_segment.name, "rb") as audio_file:
                            response = client.audio.transcriptions.create(
                                model="whisper-1",
                                file=audio_file,
                                response_format="text",
                                language="ru"
                            )

                        if response.strip():
                                    speech_detected = True
                                    first_words = ' '.join(response.strip().split()[:5])
                                    logging.info(f"[scene {scene.start:.1f}-{scene.end:.1f}, first words: {first_words}")
                        
                        speech_detected = bool(response.strip())
                        
                    except Exception as e:
                        logging.error(f"[whisper api error for scene {scene.start}-{scene.end}]: {e}")
                        speech_detected = False
                    
                    os.unlink(temp_segment.name)

                audio_data.append((scene, energy, speech_detected))

            os.unlink(temp_audio.name)


    except Exception as e:
        logging.error(f"[audio feature extraction error]: {e}")
    return audio_data

def detect_motion(video_path, scenes, motion_threshold=5000):
    """detect motion activity in each scene"""
    motion_data = []
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logging.error("failed to open video for motion detection.")
            return []

        for scene in scenes:
            cap.set(cv2.CAP_PROP_POS_MSEC, scene.start * 1000)
            _, prev_frame = cap.read()
            if prev_frame is None:
                motion_data.append((scene, 0))
                continue

            prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
            motion_activity = 0

            while cap.get(cv2.CAP_PROP_POS_MSEC) < scene.end * 1000:
                ret, curr_frame = cap.read()
                if not ret:
                    break
                curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)
                diff = cv2.absdiff(prev_gray, curr_gray)
                motion_activity += np.sum(diff > 25)
                prev_gray = curr_gray

            motion_data.append((scene, motion_activity))

        cap.release()
    except Exception as e:
        logging.error(f"[motion detection error]: {e}")
    return motion_data

def create_highlight_summary(input_path_name, output_path_name, summary_percent, weights):
    """create a highlight summary video"""
    try:
        scenes = find_scenes_opencv(input_path_name)
        if not scenes:
            raise RuntimeError("no scenes detected.")

        audio_features = extract_audio_features(input_path_name, scenes)

        motion_features = detect_motion(input_path_name, scenes)

        combined_data = [
            (scene, audio_energy, motion_activity, speech_detected)
            for ((scene, audio_energy, speech_detected), (_, motion_activity)) in zip(audio_features, motion_features)
        ]

        combined_data.sort(
            key=lambda x: calculate_scene_scores(x[0], x[1], x[2], x[3], weights),
            reverse=True
        )

        video = VideoFileClip(input_path_name)
        total_duration = video.duration
        target_summary_length = total_duration * summary_percent

        selected_scenes = []
        accumulated_duration = 0
        for scene, audio_energy, motion_activity, speech_detected in combined_data:
            scene_length = scene.end - scene.start
            if accumulated_duration + scene_length <= target_summary_length:
                selected_scenes.append(scene)
                accumulated_duration += scene_length
            if accumulated_duration >= target_summary_length:
                break

        min_scenes = 7
        if len(selected_scenes) < min_scenes:
            additional_scenes = [sc[0] for sc in combined_data if sc[0] not in selected_scenes]
            selected_scenes.extend(additional_scenes[:min_scenes - len(selected_scenes)])

        selected_scenes.sort(key=lambda scene: scene.start)

        summary_clips = [video.subclipped(scene.start, scene.end) for scene in selected_scenes]
        summary = concatenate_videoclips(summary_clips)

        summary.write_videofile(output_path_name, codec="libx264", fps=24, audio_codec="aac")

    except Exception as e:
        logging.error(f"error in summary creation: {e}")
        return None

def save_scenes(input_path_name, output_directory):
    """save detected scenes as individual video clips"""
    os.makedirs(output_directory, exist_ok=True)
    
    scenes = find_scenes_opencv(
        input_path_name, 
        diff_threshold=0.2,
        scene_detection_skip=1,
        min_scene_duration=0.5,
        motion_threshold=0.05
    )
    
    video = VideoFileClip(input_path_name)
    
    for i, scene in enumerate(scenes):
        clip = video.subclipped(scene.start, scene.end)
        output_path = os.path.join(output_directory, f"scene_{i+1}.mp4")
        clip.write_videofile(output_path, codec='libx264')
    
    video.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Video Summarization Script")
    parser.add_argument('input_video', type=str, help="Path to the input video file")
    parser.add_argument('output_directory', type=str, help="Path to the output directoty")

    args = parser.parse_args()
    save_scenes(args.input_video, args.output_directory)