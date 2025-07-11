import os
import whisper
import argparse
import re
import json
from pydub import AudioSegment
import subprocess

class RegexpProc(object):
    PATTERN_1 = r''.join((
        r'\w{0,5}[хx]([хx\s\!@#\$%\^&*+-\|\/]{0,6})',
        r'[уy]([уy\s\!@#\$%\^&*+-\|\/]{0,6})[ёiлeеюийя]\w{0,7}|\w{0,6}[пp]',
        r'([пp\s\!@#\$%\^&*+-\|\/]{0,6})[iие]([iие\s\!@#\$%\^&*+-\|\/]{0,6})',
        r'[3зс]([3зс\s\!@#\$%\^&*+-\|\/]{0,6})[дd]\w{0,10}|[сcs][уy]',
        r'([уy\s\!@#\$%\^&*+-\|\/]{0,6})[4чkк]\w{1,3}|\w{0,4}[bб]',
        r'([bб\s\!@#\$%\^&*+-\|\/]{0,6})[lл]([lл\s\!@#\$%\^&*+-\|\/]{0,6})',
        r'[yя]\w{0,10}|\w{0,8}[её][bб][лске@eыиаa][наи@йвл]\w{0,8}|\w{0,4}[еe]',
        r'([еe\s\!@#\$%\^&*+-\|\/]{0,6})[бb]([бb\s\!@#\$%\^&*+-\|\/]{0,6})',
        r'[uу]([uу\s\!@#\$%\^&*+-\|\/]{0,6})[н4ч]\w{0,4}|\w{0,4}[еeё]',
        r'([еeё\s\!@#\$%\^&*+-\|\/]{0,6})[бb]([бb\s\!@#\$%\^&*+-\|\/]{0,6})',
        r'[нn]([нn\s\!@#\$%\^&*+-\|\/]{0,6})[уy]\w{0,4}|\w{0,4}[еe]',
        r'([еe\s\!@#\$%\^&*+-\|\/]{0,6})[бb]([бb\s\!@#\$%\^&*+-\|\/]{0,6})',
        r'[оoаa@]([оoаa@\s\!@#\$%\^&*+-\|\/]{0,6})[тnнt]\w{0,4}|\w{0,10}[ё]',
        r'([ё\s\!@#\$%\^&*+-\|\/]{0,6})[б]\w{0,6}|\w{0,4}[pп]',
        r'([pп\s\!@#\$%\^&*+-\|\/]{0,6})[иeеi]([иeеi\s\!@#\$%\^&*+-\|\/]{0,6})',
        r'[дd]([дd\s\!@#\$%\^&*+-\|\/]{0,6})[oоаa@еeиi]',
        r'([oоаa@еeиi\s\!@#\$%\^&*+-\|\/]{0,6})[рr]\w{0,12}',
    ))
    PATTERN_2 = r'|'.join((
        r"(\b[сs]{1}[сsц]{0,1}[uуy](?:[ч4]{0,1}[иаakк][^ц])\w*\b)",
        r"(\b(?!пло|стра|[тл]и)(\w(?!(у|пло)))*[хx][уy](й|йа|[еeё]|и|я|ли|ю)(?!га)\w*\b)",
        r"(\b(п[oо]|[нз][аa])*[хx][eе][рp]\w*\b)",
        r"(\b[мm][уy][дd]([аa][кk]|[oо]|и)\w*\b)",
        r"(\b\w*д[рp](?:[oо][ч4]|[аa][ч4])(?!л)\w*\b)",
        r"(\b(?!(?:кило)?[тм]ет)(?!смо)[а-яa-z]*(?<!с)т[рp][аa][хx]\w*\b)",
        r"(\b[к|k][аaoо][з3z]+[eе]?ё?л\w*\b)",
        r"(\b(?!со)\w*п[еeё]р[нд](и|иc|ы|у|н|е|ы)\w*\b)",
        r"(\b\w*[бп][ссз]д\w+\b)",
        r"(\b([нnп][аa]?[оo]?[xх])\b)",
        r"(\b([аa]?[оo]?[нnпбз][аa]?[оo])?([cс][pр][аa][^зжбсвм])\w*\b)",            
        r"(\b\w*([оo]т|вы|[рp]и|[оo]|и|[уy]){0,1}([пnрp][iиеeё]{0,1}[3zзсcs][дd])\w*\b)",
        r"(\b(вы)?у?[еeё]?би?ля[дт]?[юоo]?\w*\b)",
        r"(\b(?!вело|ски|эн)\w*[пpp][eеиi][дd][oaоаеeирp](?![цянгюсмйчв])[рp]?(?![лт])\w*\b)",
        r"(\b(?!в?[ст]{1,2}еб)(?:(?:в?[сcз3о][тяaа]?[ьъ]?|вы|п[рp][иоo]|[уy]|р[аа][з3z][ьъ]?|к[оo]н[оo])?[её]б[а-яa-z]*)|(?:[а-яa-z]*[^хлрдв][еeё]б)\b)",            
        r"(\b[з3z][аaоo]л[уy]п[аaeеин]\w*\b)",
    ))
    regexp = re.compile(PATTERN_1 + '|' + PATTERN_2, re.U | re.I)

def extract_audio_from_video(video_path, output_audio_path):
    """extract audio from video using ffmpeg"""
    command = f'ffmpeg -i "{video_path}" -q:a 0 -map a "{output_audio_path}" -y'
    subprocess.call(command, shell=True)
    return output_audio_path

def find_curse_words_timestamps(transcript):
    """find timestamps of curse words in transcript"""
    curse_timestamps = []
    processed_words = set()
    
    for segment in transcript["segments"]:
        if "words" in segment:
            for word_data in segment["words"]:
                word = word_data["word"]
                word_id = f"{word}_{word_data['start']}"
                
                if word_id in processed_words:
                    continue
                
                match = RegexpProc.regexp.search(word)
                if match:
                    profane_part = match.group(0)
                    profane_start_idx = match.start()
                    profane_end_idx = match.end()
                    
                    word_duration = word_data["end"] - word_data["start"]
                    
                    if profane_part != word and len(word) > 0:
                        profane_start_ratio = profane_start_idx / len(word)
                        profane_end_ratio = profane_end_idx / len(word)
                        
                        profane_start_time = word_data["start"] + (word_duration * profane_start_ratio)
                        profane_end_time = word_data["start"] + (word_duration * profane_end_ratio)
                    else:
                        profane_start_time = word_data["start"]
                        profane_end_time = word_data["end"]
                    
                    curse_timestamps.append({
                        'word': word,
                        'profane_part': profane_part,
                        'start_time': profane_start_time,
                        'end_time': profane_end_time
                    })
                    
                    processed_words.add(word_id)
    
    return curse_timestamps

def mask_curse_words(audio_path, curse_timestamps, mask_audio_path, output_path):
    """add mask sound at curse word positions"""
    original_audio = AudioSegment.from_file(audio_path)
    mask_sound = AudioSegment.from_file(mask_audio_path) - 20
    
    result_audio = original_audio
    
    curse_timestamps = sorted(curse_timestamps, key=lambda x: x['start_time'])
    
    masked_segments = []
    
    for curse in curse_timestamps:
        start_ms = int(curse['start_time'] * 1000)
        end_ms = int(curse['end_time'] * 1000)
        
        if end_ms <= start_ms:
            continue
            
        duration_ms = end_ms - start_ms
        
        masked_segments.append((start_ms, end_ms))
        
        if len(mask_sound) > duration_ms:
            adjusted_mask = mask_sound[:duration_ms]
        else:
            adjusted_mask = mask_sound
        
        keep_edges_ms = duration_ms // 4 

        mask_start = start_ms + keep_edges_ms
        mask_end = end_ms - keep_edges_ms

        result_audio = result_audio[:mask_start] + adjusted_mask + result_audio[mask_end:]

    
    result_audio.export(output_path, format="mp3")
    return output_path

def replace_audio_in_video(video_path, audio_path, output_video_path):
    """replace audio in video with censored audio"""
    command = f'ffmpeg -i "{video_path}" -i "{audio_path}" -c:v copy -map 0:v:0 -map 1:a:0 "{output_video_path}" -y'
    subprocess.call(command, shell=True)
    return output_video_path

def censor_video(video_path, mask_audio_path="peekaboo.mp3", output_path=None):
    """censor curse words in video"""
    if output_path is None:
        base, ext = os.path.splitext(video_path)
        
        output_path = f"{base}_censored{ext}"
    
    temp_audio = "temp_extracted_audio.wav"
    censored_audio = "temp_censored_audio.mp3"
    
    try:
        extract_audio_from_video(video_path, temp_audio)
        
        if not os.path.exists("current_transcript.json"):
            model = whisper.load_model("medium")
            transcript = model.transcribe(
                video_path, 
                language="russian",
                word_timestamps=True
            )
            with open("current_transcript.json", "w", encoding="utf-8") as f:
                json.dump(transcript, f, ensure_ascii=False)
        else:
            with open("current_transcript.json", "r", encoding="utf-8") as f:
                transcript = json.load(f)
        curse_timestamps = find_curse_words_timestamps(transcript)
        
        if curse_timestamps:
            print(f"found {len(curse_timestamps)} curse words to censor:")
            for curse in curse_timestamps:
                print(f"  - '{curse['word']}' (censoring '{curse['profane_part']}') at {curse['start_time']:.2f}s to {curse['end_time']:.2f}s")
            
            mask_curse_words(temp_audio, curse_timestamps, mask_audio_path, censored_audio)
            
            replace_audio_in_video(video_path, censored_audio, output_path)
            
            print(f"censored video saved to: {output_path}")
        else:
            print("no curse words found!")
            with open(video_path, 'rb') as src, open(output_path, 'wb') as dst:
                dst.write(src.read())
    
    finally:
        for temp_file in [temp_audio, censored_audio]:
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    return output_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Censor profanity in video by masking audio")
    parser.add_argument("--input", required=True, help="Input video file path")
    parser.add_argument("--mp3", required=True, help="MP3 mask path")
    parser.add_argument("--output", required=True, help="Output video file path")
    
    args = parser.parse_args()    
    print(f"processing: {args.input}")
    
    try:
        censor_video(args.input, args.mp3, args.output)
        print(f"successfully masked video: {args.output}")
    except Exception as e:
        print(f"error processing video: {e}")