import os
from flask import Flask, request, redirect, url_for, send_from_directory, render_template
from werkzeug.utils import secure_filename
import speech_recognition as sr
from pydub import AudioSegment, silence
import pandas as pd
from moviepy.editor import VideoFileClip

UPLOAD_FOLDER = 'static'
ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        process_video(file_path)  # ビデオ処理を行う
        return redirect(url_for('video_page', video_filename=filename))

@app.route('/<video_filename>')
def video_page(video_filename):
    csv_file_path = os.path.join('static', 'transcription.csv')
    if not os.path.exists(csv_file_path):
        return "Video is still being processed. Please wait and refresh the page."
    return render_template('dealed_movie.html', video_filename=video_filename)

@app.route('/transcription')
def transcription():
    return send_from_directory('static', 'transcription.csv')

def process_video(video_file_path):
    # MP4ファイルから音声を抽出してWAV形式に変換
    video = VideoFileClip(video_file_path)
    audio = video.audio
    audio_file_path = "extracted_audio.wav"
    audio.write_audiofile(audio_file_path, codec='pcm_s16le')

    # 音声ファイルを読み込み
    audio_segment = AudioSegment.from_wav(audio_file_path)

    # 無音部分を検出
    silence_thresh = audio_segment.dBFS - 18
    chunks = silence.split_on_silence(audio_segment, min_silence_len=500, silence_thresh=silence_thresh)

    # 音声認識の準備
    recognizer = sr.Recognizer()

    # CSV用のリスト
    data = []

    # 無音部分の検出結果を保存
    nonsilent_intervals = silence.detect_nonsilent(audio_segment, min_silence_len=500, silence_thresh=silence_thresh)

    # チャンク毎に処理
    for i, chunk in enumerate(chunks):
        chunk_filename = f"chunk{i}.wav"
        # チャンクを一時ファイルに保存
        chunk.export(chunk_filename, format="wav")

        # チャンクの音声ファイルを認識
        with sr.AudioFile(chunk_filename) as source:
            audio_data = recognizer.record(source)
            try:
                text = recognizer.recognize_google(audio_data, language="ja-JP")
                start_time = nonsilent_intervals[i][0] // 1000  # ミリ秒を秒に変換し整数化
                end_time = nonsilent_intervals[i][1] // 1000  # ミリ秒を秒に変換し整数化
                data.append({"start_time": start_time, "end_time": end_time, "text": text})
            except sr.UnknownValueError:
                continue  # 無視する
            except sr.RequestError as e:
                start_time = nonsilent_intervals[i][0] // 1000  # ミリ秒を秒に変換し整数化
                end_time = nonsilent_intervals[i][1] // 1000  # ミリ秒を秒に変換し整数化
                data.append({"start_time": start_time, "end_time": end_time, "text": f"Error: {e}"})

        # チャンクファイルを削除
        os.remove(chunk_filename)

    df = pd.DataFrame(data)
    csv_file_path = os.path.join('static', 'transcription.csv')
    df.to_csv(csv_file_path, index=False)

    os.remove(audio_file_path)
if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
app.run(debug=True)