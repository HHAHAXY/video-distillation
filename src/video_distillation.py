import cv2
import os
import numpy as np
import pandas as pd
from tqdm import tqdm

PATH2VID = "/Users/rusiq/Downloads/youtube_dl/katka1.mp4"


def process_optical_flow(PATH2VID, output_csv="motion_intensity.csv", output_video="optical_flow_video.mp4"):
    """process video for optical flow and motion intensity"""

    cap = cv2.VideoCapture(PATH2VID)
    if not cap.isOpened():
        raise ValueError(f"could not open video file: {PATH2VID}")
    
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    frame_duration = 1.0 / fps
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_video, fourcc, fps, (frame_width, frame_height))

    ret, prev_frame = cap.read()
    if not ret:
        raise ValueError("failed to read the first frame.")
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    motion_data = []

    frame_index = 0
    with tqdm(total=total_frames/100, desc="Processing") as pbar:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            curr_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            flow = cv2.calcOpticalFlowFarneback(
                prev=prev_gray,
                next=curr_gray,
                flow=None,
                pyr_scale=0.5,
                levels=3,
                winsize=15,
                iterations=3,
                poly_n=5,
                poly_sigma=1.1,
                flags=cv2.OPTFLOW_FARNEBACK_GAUSSIAN
            )

            magnitude, angle = cv2.cartToPolar(flow[..., 0], flow[..., 1])
            
            motion_data.append({"frame": frame_index, 
                                "time": frame_index * frame_duration, 
                                "mean_motion_intensity": np.mean(magnitude),
                                "median_motion_intensity": np.median(magnitude),
                                "motion_std_dev": np.std(magnitude)
                                })

            flow_hsv = np.zeros_like(frame)
            flow_hsv[..., 0] = cv2.normalize(angle, None, 0, 179, cv2.NORM_MINMAX)
            flow_hsv[..., 1] = 255
            flow_hsv[..., 2] = cv2.normalize(magnitude, None, 0, 255, cv2.NORM_MINMAX)

            flow_bgr = cv2.cvtColor(flow_hsv, cv2.COLOR_HSV2BGR)

            overlay_frame = cv2.addWeighted(frame, 0.7, flow_bgr, 0.3, 0)

            cv2.putText(overlay_frame, f'avg motion intensity: {round(np.mean(magnitude), 2)}', 
                        (10, frame_height - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            
            out.write(overlay_frame)
            
            prev_gray = curr_gray
            frame_index += 1

            if frame_index % 100 == 0:
                pbar.update(1)

    
    motion_df = pd.DataFrame(motion_data)
    motion_df.to_csv(output_csv, index=False)
    print(f"motion intensity data saved to {output_csv}")

    cap.release()
    out.release()
    print(f"optical flow video saved to {output_video}")

if __name__ == '__main__':
    process_optical_flow(PATH2VID)
    print("here")