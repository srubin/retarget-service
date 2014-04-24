import sys
import os.path
import glob

from flask import Flask, jsonify, abort
from werkzeug import secure_filename
import eyed3

import radiotool.algorithms.constraints as rt_constraints
from radiotool.algorithms import retarget
from radiotool.composer import Song

app = Flask(__name__)
app.debug = True


try:
    from app_path import APP_PATH
except:
    APP_PATH = ''

UPLOAD_PATH = 'static/uploads/'
upload_path = os.path.join(APP_PATH, UPLOAD_PATH)


@app.route('/')
def ping():
    return "pong"


@app.route('/uploadTrack', methods=['POST'])
def upload_song():

    # POST part
    f = request.files['song']
    file_path = f.filename.replace('\\', '/')
    basename = os.path.basename(file_path)
    filename = secure_filename(f.filename)
    full_name = os.path.join(upload_path, filename)
    f.save(full_name)

    # get id3 tags
    song = eyed3.load(full_name)
    song_title = song.tag.title
    song_artist = song.tag.artist

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
        "filename": filename,
        "name": basename.split('.')[0],
        "title": song_title,
        "artist": song_artist,
        "basename": os.path.splitext(filename)[0]
    }

    # get length of song upload
    track = Track(wav_name, "track")
    out["dur"] = track.total_frames() / float(track.samplerate) * 1000.0

    return jsonify(**out)


@app.route('/retarget/<filename>/<duration>')
@app.route('/retarget/<filename>/<duration>/<start>/<end>')
def retarget(filename, duration, start=True, end=True):
    try:
        duration = float(duration)
    except:
        abort(400)
    song_path = os.path.join(upload_path, filename)
    try:
        song = Song(song_path)
    except:
        abort(403)

    return "woop" 


if __name__ == "__main__":
    app.run(port=8080)
