import sys
sys.path.append("/var/www/html/srubin/retargeting/retarget-service")

import glob
import os
import os.path
import subprocess
import time
import uuid

from celery import Celery
from celery.result import from_serializable
from flask import Flask, jsonify, abort, request, session
from mutagen.easyid3 import EasyID3
from werkzeug import secure_filename
import numpy as N

from radiotool.algorithms import retarget as rt_retarget
from radiotool.composer import Song, Segment, RawTrack
import radiotool.algorithms.constraints as rt_constraints

app = Flask(__name__)
app.debug = True

celery = Celery('retarget-service')
celery.config_from_object('celeryconfig')
# celery.conf.update(app.config)

try:
    from app_path import APP_PATH
except:
    APP_PATH = ''

UPLOAD_PATH = 'static/uploads/'
upload_path = os.path.join(APP_PATH, UPLOAD_PATH)

STOCK_PATH = 'static/stock/'
stock_path = os.path.join(APP_PATH, STOCK_PATH)

RESULT_PATH = 'static/generated/'
result_path = os.path.join(APP_PATH, RESULT_PATH)

CACHE_DIR = 'featurecache/'
cache_dir = os.path.join(APP_PATH, CACHE_DIR)

MOUNT_PATH = ''
try:
    from app_path import APP_URL
except:
    APP_URL = ''
    MOUNT_PATH = '/retarget-service'


@app.route('/')
def ping():
    return "pong"


@app.route(MOUNT_PATH + '/uploadTrack', methods=['POST'])
def upload_song():
    session.clear()
    print "Uploading track"
    # POST part
    f = request.files['song']
    file_path = f.filename.replace('\\', '/')
    basename = os.path.basename(file_path)
    filename = secure_filename(f.filename)
    full_name = os.path.join(upload_path, filename)
    f.save(full_name)

    # get id3 tags
    song = EasyID3(full_name)
    try:
        song_title = song["title"]
    except:
        song_title = "Track name"
    # song_artist = song["artist"]

    wav_name = ".".join(full_name.split('.')[:-1]) + '.wav'

    # convert to wav if necessary
    try:
        with open(wav_name):
            pass
    except IOError:
        subprocess.call(
            'lame --decode "{}"'.format(full_name),
            shell=True)

    out = {
        "name": basename.split('.')[0],
        "title": song_title,
        # "artist": song_artist,
        "filename": os.path.splitext(filename)[0] + '.wav'
    }

    song_path = os.path.join(upload_path, out["filename"])
    song = Song(song_path, cache_dir=cache_dir)
    out["duration"] = song.duration_in_seconds,

    return jsonify(**out)


@app.route(MOUNT_PATH + '/retarget/<filename>/<source>/<duration>')
@app.route(MOUNT_PATH + '/retarget/<filename>/<source>/<duration>/<start>/<end>')
def retarget(filename, source, duration, start="start", end="end"):
    print "Retargeting track: {}".format(filename)

    if source == 'stock':
        song_path = os.path.join(stock_path, filename)
    else:
        song_path = os.path.join(upload_path, filename)

    try:
        song = Song(song_path, cache_dir=cache_dir)
    except:
        abort(403)

    if not song.features_cached():
        print "Analyzing track"
        analyze_track(song_path)

    try:
        duration = float(duration)
    except:
        abort(400)

    constraints = [
        rt_constraints.TimbrePitchConstraint(
            context=0, timbre_weight=1.0, chroma_weight=1.0),
        rt_constraints.EnergyConstraint(penalty=.5),
        rt_constraints.MinimumLoopConstraint(8),
    ]

    extra = ''

    if start == "start":
        constraints.append(
            rt_constraints.StartAtStartConstraint(padding=0))
        extra += 'Start'
    if end == "end":
        constraints.append(
            rt_constraints.EndAtEndConstraint(padding=12))
        extra += 'End'

    comp, info = rt_retarget.retarget(
        [song], duration, constraints=[constraints],
        fade_in_len=None, fade_out_len=None)

    # force the new track to extend to the end of the song
    if end == "end":
        last_seg = sorted(
            comp.segments,
            key=lambda seg:
            seg.comp_location_in_seconds + seg.duration_in_seconds
        )[-1]
        last_seg.duration_in_seconds = (
            song.duration_in_seconds - last_seg.start_in_seconds)

    uid = str(uuid.uuid4())

    result_fn = "{}-{}-{}-{}".format(
        os.path.splitext(filename)[0],
        str(duration),
        extra,
        uid)

    result_full_fn = os.path.join(result_path, result_fn)

    # if end == "end":
    #     frames = comp.build(channels=song.channels)
    #     new_track = time_stretch(frames, song.samplerate, duration)
    #     comp = Composition(channels=song.channels)
    #     comp.add_segment(
    #         Segment(new_track, 0.0, 0.0, new_track.duration_in_seconds))

    comp.export(filename=result_full_fn,
                channels=song.channels,
                filetype='mp3')

    print info["transitions"]

    result_url = os.path.join(APP_URL, RESULT_PATH)
    result_url = os.path.join(result_url, result_fn)

    path_cost = info["path_cost"]
    total_nonzero_cost = []
    total_nonzero_points = []
    for node in path_cost:
        if float(node.name) > 0.0:
            total_nonzero_cost.append(float(node.name))
            total_nonzero_points.append(float(node.time))

    transitions = zip(total_nonzero_points, total_nonzero_cost)

    out = {
        "url": result_url + '.mp3',
        "transitions": [[round(t[0], 1), round(t[1], 2)] for t in transitions]
    }

    return jsonify(**out)


# way too slow for this demo:

# def time_stretch(frames, samplerate, target_duration):
#     n_fft = 2048
#     hop_length = n_fft / 4

#     scale_factor = float(target_duration) / len(frames) / float(samplerate)

#     D = librosa.stft(frames, n_fft=n_fft, hop_length=hop_length)
#     D_stretch = librosa.phase_vocoder(
#         D, scale_factor, hop_length=hop_length)
#     y_stretch = librosa.istft(D_stretch, hop_length=hop_length)
#     return RawTrack(y_stretch, samplerate=samplerate)


@celery.task
def analyze_track(filename):
    song = Song(filename, cache_dir=cache_dir)
    _ = song.analysis["beats"]
    return True

app.secret_key = "\xdf!\xf7\xb81'L\xbf\x95\x93"\
    "\x9f\xdd_|\xb6\xf9\xb2\xf2[\x9e\xfd\xf5\xf3\xef"


@celery.task
def clean_generated():
    now = time.time()
    for f in glob.glob(RESULT_PATH + '*.mp3'):
        if os.stat(f).st_mtime < now - 1 * 86400:
            if os.path.isfile(f):
                os.remove(f)


@celery.task
def clean_uploads():
    now = time.time()
    for f in glob.glob(UPLOAD_PATH + '*.mp3'):
        if os.stat(f).st_mtime < now - 1 * 86400:
            if os.path.isfile(f):
                os.remove(f)
    for f in glob.glob(UPLOAD_PATH + '*.wav'):
        if os.stat(f).st_mtime < now - 1 * 86400:
            if os.path.isfile(f):
                os.remove(f)


if __name__ == "__main__":
    app.run(port=8080)
