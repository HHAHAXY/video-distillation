# Video Distillation

**Note:** This project is under development and not complete.

This project is a python video summarization tool. It uses computer vision and audio analysis to create highlight reels from videos. It analyzes video content for scene changes, motion, and speech to find key moments.

## Features

### Video Analysis & Processing

*   **Scene Detection:** Scene boundary detection using optical flow ✅.
*   **Motion Analysis:** Optical flow and motion intensity measurement ✅.
*   **Audio Energy Analysis:** RMS energy and audio-based video trimming ✅.
*   **Speech Detection:** Voice activity detection using silero vad and whisper transcription ✅.

### Content Detection & Moderation

*   **Profanity Detection:** Automatic censoring of language in videos ✅.
*   **Copyright Detection:** Music fingerprinting using acoustid for copyright compliance 🚧.
*   **Counter Detection:** OCR-based detection of changing numbers in videos ✅.
*   **Content Summarization:** AI-powered highlight generation based on multiple metrics 🚧.

### YouTube Integration

*   **Video Upload:** Automated youtube upload with metadata 🚧.
*   **Content ID Checking:** Youtube content id claim status verification 🚧.
*   **Privacy Controls:** Configurable upload privacy settings 🚧.

## Project Structure

The project is organized as follows:

*   `src/`: Core python source code for video distillation.
*   `notebooks/`: Jupyter notebooks for experimentation and analysis.
*   `scripts/`: Standalone utility scripts.
*   `data/`: Data files like csvs and jsons.

## Getting Started

### Prerequisites

*   Python 3.9+
*   FFmpeg

### Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/your-username/video-distillation.git
    ```
2.  Install python packages:
    ```bash
    pip install -r requirements.txt
    ```
3.  Set up api keys as environment variables:
    ```bash
    export OPENAI_API_KEY="your-openai-api-key"
    export ACOUSTID_API_KEY="your-acoustid-api-key"
    ```

### Usage

To generate a video summary, run the `app.py` script from `src`:

```bash
python src/app.py <input_video_path> <output_directory>
```

## Contributing

Contributions are welcome. Submit a pull request or open an issue for suggestions or bugs.
