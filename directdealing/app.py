import os
import cv2
import numpy as np
from flask import Flask, Response, render_template, redirect, url_for, jsonify, request, send_from_directory
import threading
import pyaudio
import wave
import time
import speech_recognition as sr
from pydub import AudioSegment, silence
import pandas as pd
import subprocess

app = Flask(__name__)

UPLOAD_FOLDER = 'static'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

camera = None
out = None
is_recording = False
recording_thread = None

audio_file_path = 'static/audio.wav'
video_file_path = 'static/output.mp4'
combined_file_path = 'static/combined_output.mp4'
extracted_audio_path = 'static/extracted_audio.wav'

def record_audio():
    global is_recording, audio_file_path
    audio_format = pyaudio.paInt16
    channels = 1
    rate = 44100
    chunk = 1024

    p = pyaudio.PyAudio()
    stream = p.open(format=audio_format, channels=channels, rate=rate, input=True, frames_per_buffer=chunk)

    frames = []

    while is_recording:
        data = stream.read(chunk)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    p.terminate()

    wf = wave.open(audio_file_path, 'wb')
    wf.setnchannels(channels)
    wf.setsampwidth(p.get_sample_size(audio_format))
    wf.setframerate(rate)
    wf.writeframes(b''.join(frames))
    wf.close()

def record_video():
    global camera, out, is_recording
    while is_recording:
        ret, frame = camera.read()
        if ret:
            out.write(frame)
        else:
            break

def reencode_video(video_path):
    global combined_file_path
    output_path = 'static/reencoded_output.mp4'
    command = f"ffmpeg -i {video_path} -c:v libx264 -crf 23 -preset medium -c:a aac -b:a 128k {output_path}"
    subprocess.call(command, shell=True)
    return output_path

@app.route('/')
def index():
    return render_template('index.html')

def generate_frames():
    global camera
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        raise Exception("Could not open video device")
    try:
        while True:
            time.sleep(0.1)  # Adjust waiting time if needed
            success, frame = camera.read()
            if not success:
                break
            else:
                ret, buffer = cv2.imencode('.jpg', frame)
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    finally:
        camera.release()

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/start_recording')
def start_recording():
    global camera, out, is_recording, recording_thread
    if not is_recording:
        is_recording = True
        camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            return jsonify({"status": "Error", "message": "Could not open video device"}), 500
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(video_file_path, fourcc, 60.0, (1280, 720))

        recording_thread = threading.Thread(target=record_video)
        audio_thread = threading.Thread(target=record_audio)

        recording_thread.start()
        audio_thread.start()
    return jsonify({"status": "Recording started"})

@app.route('/stop_recording')
def stop_recording():
    global is_recording, camera, out, recording_thread
    is_recording = False
    if recording_thread:
        recording_thread.join()  # Wait for the recording thread to finish
    if out:
        out.release()

    # Combine video and audio
    combine_video_audio(video_file_path, audio_file_path)

    # Extract audio from combined video
    extract_audio(combined_file_path, extracted_audio_path)

    # Process the extracted audio for transcription
    process_audio(extracted_audio_path)

    # Re-encode combined video if needed
    reencode_video(combined_file_path)

    print(f"Recording stopped. Combined video filename: {combined_file_path}")  # デバッグ情報
    return jsonify({"status": "Recording stopped", "video_url": url_for('view_video')})

def process_audio(audio_path):
    try:
        # Load audio using pydub
        audio_segment = AudioSegment.from_wav(audio_path)

        # Detect silence and split audio into chunks
        silence_thresh = audio_segment.dBFS - 13
        chunks = silence.split_on_silence(audio_segment, min_silence_len=500, silence_thresh=silence_thresh)

        # Speech recognition setup
        recognizer = sr.Recognizer()
        data = []

        # Detect non-silent intervals
        nonsilent_intervals = silence.detect_nonsilent(audio_segment, min_silence_len=500, silence_thresh=silence_thresh)

        # Process each chunk
        for i, chunk in enumerate(chunks):
            chunk_filename = f"chunk{i}.wav"
            chunk.export(chunk_filename, format="wav")

            # Recognize speech in the chunk
            with sr.AudioFile(chunk_filename) as source:
                audio_data = recognizer.record(source)
                try:
                    text = recognizer.recognize_google(audio_data, language="ja-JP")
                    start_time = nonsilent_intervals[i][0] // 1000
                    end_time = nonsilent_intervals[i][1] // 1000
                    data.append({"start_time": start_time, "end_time": end_time, "text": text})
                except sr.UnknownValueError:
                    continue
                except sr.RequestError as e:
                    start_time = nonsilent_intervals[i][0] // 1000
                    end_time = nonsilent_intervals[i][1] // 1000
                    data.append({"start_time": start_time, "end_time": end_time, "text": f"Error: {e}"})

            # Remove the chunk file
            os.remove(chunk_filename)

        # Save transcription to CSV
        df = pd.DataFrame(data)
        csv_file_path = os.path.join('static', 'transcription.csv')
        df.to_csv(csv_file_path, index=False)

    except Exception as e:
        print(f"Failed to process audio: {e}")
        return

def combine_video_audio(video_path, audio_path):
    global combined_file_path
    command = f"ffmpeg -i {video_path} -i {audio_path} -c:v copy -c:a aac -strict experimental {combined_file_path}"
    subprocess.call(command, shell=True)

def extract_audio(video_path, audio_output_path):
    command = f"ffmpeg -i {video_path} -q:a 0 -map a {audio_output_path}"
    subprocess.call(command, shell=True)

@app.route('/view_video')
def view_video():
    video_filename = "reencoded_output.mp4"  # Re-encoded video filename
    video_url = url_for('static', filename=video_filename, t=int(time.time()))
    return render_template('dealed_movie.html', video_url=video_url, mimetype="video/mp4")

if __name__ == '__main__':
    app.run(debug=True, host="10.96.126.108", port=5000)
