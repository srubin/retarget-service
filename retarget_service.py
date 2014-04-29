import sys
sys.path.append("/var/www/html/srubin/retargeting/retarget-service")

import os.path
import os
import glob
import subprocess
import time

from flask import Flask, jsonify, abort, request, session
from werkzeug import secure_filename
from mutagen.easyid3 import EasyID3
from celery import Celery
from celery.result import from_serializable

import radiotool.algorithms.constraints as rt_constraints
from radiotool.algorithms import retarget as rt_retarget
from radiotool.composer import Song

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

RESULT_PATH = 'static/generated/'
result_path = os.path.join(APP_PATH, RESULT_PATH)

CACHE_DIR = 'featurecache/'
cache_dir = os.path.join(APP_PATH, CACHE_DIR)

try:
    from app_path import APP_URL
except:
    APP_URL = ''


@app.route('/')
def ping():
    return "pong"


@app.route('/uploadTrack', methods=['POST'])
def upload_song():
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

    # run the analysis asynchronously using Celery
    result = analyze_track.delay(
        os.path.join(upload_path, out["filename"]))

    session_key = 'analysis_{}'.format(out["filename"])

    session[session_key] = result.serializable()

    return jsonify(**out)


@app.route('/retarget/<filename>/<duration>')
@app.route('/retarget/<filename>/<duration>/<start>/<end>')
def retarget(filename, duration, start="start", end="end"):
    print "Retargeting track: {}".format(filename)
    session_key = 'analysis_{}'.format(filename)
    if session_key in session:
        print "Getting {}".format(session_key)
        if from_serializable(session[session_key]).ready():
            session.pop(session_key, None)
        else:
            from_serializable(session[session_key]).get()
            session.pop(session_key, None)
    else:
        print "Could not file celery task for {}".format(session_key)
    print "Proceeding to retarget"

    try:
        duration = float(duration)
    except:
        abort(400)
    song_path = os.path.join(upload_path, filename)
    try:
        song = Song(song_path, cache_dir=cache_dir)
    except:
        abort(403)

    constraints = [
        rt_constraints.TimbrePitchConstraint(
            context=0, timbre_weight=1.0, chroma_weight=1.0),
        rt_constraints.EnergyConstraint(penalty=.5),
        rt_constraints.MinimumLoopConstraint(8),
        # rt_constraints.RandomJitterConstraint(),
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
        [song], duration, constraints=[constraints])

    result_fn = "{}-{}-{}".format(
        os.path.splitext(filename)[0],
        str(duration),
        extra)

    result_full_fn = os.path.join(result_path, result_fn)

    comp.export(filename=result_full_fn,
                channels=song.channels,
                filetype='mp3')

    print info["transitions"]

    result_url = os.path.join(APP_URL, RESULT_PATH)
    result_url = os.path.join(result_url, result_fn)

    path_cost = info["path_cost"]
    total_nonzero_cost = 0.0
    total_nonzero_points = 0
    for node in path_cost:
        if node > 0.0:
            total_nonzero_cost += float(node.name)
            total_nonzero_points += 1

    out = {
        "url": result_url + '.mp3',
        "cost": total_nonzero_cost,
        "transitions": [t.time for t in info["transitions"]]
    }

    return jsonify(**out)


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
