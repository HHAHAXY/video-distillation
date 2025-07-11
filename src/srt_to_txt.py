import re

PATH2SRT = "/Users/rusiq/Downloads/test.srt"
PATH2TXT = "/Users/rusiq/Downloads/test.txt"

def srt_to_plain_text(srt_file, output_file):
    with open(srt_file, 'r', encoding='utf-8') as file:
        text = file.read()

    text = re.sub(r'\d+\n\d{2}:\d{2}:\d{2},\d+ --> \d{2}:\d{2}:\d{2},\d+\n', '', text)
    text = re.sub(r'\n+', ' ', text).strip()

    words = text.split()
    formatted_text = ''
    for i in range(0, len(words), 10):
        formatted_text += ' '.join(words[i:i+10]) + '\n'

    with open(output_file, 'w', encoding='utf-8') as file:
        file.write(formatted_text)

srt_to_plain_text(PATH2SRT, PATH2TXT)