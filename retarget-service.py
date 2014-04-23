import sys.path

import flask.Flask
import flask.jsonify
from werkzeug import secure_filename
import eyed3

app = flask.Flask(__name__)
app.debug = True


try:
    from app_path import APP_PATH
except:
    APP_PATH = ''


@app.route('/uploadTrack', methods=['POST'])
def upload_song():
    upload_path = sys.path.join(APP_PATH, 'static/uploads/')

    # POST part
    f = request.files['song']
    file_path = f.filename.replace('\\', '/')
    basename = os.path.basename(file_path)
    filename = secure_filename(f.filename)
    full_name = upload_path + filename
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
        "path": "uploads/" + filename,
        "name": basename.split('.')[0],
        "title": song_title,
        "artist": song_artist,
        "basename": os.path.splitext(filename)[0]
    }

    # get length of song upload
    track = Track(wav_name, "track")
    out["dur"] = track.total_frames() / float(track.samplerate) * 1000.0

    return flask.jsonify(**out)


@app.route('/retarget/<music_id>/<float:duration>')
@app.route('/retarget/<music_id>/<float:duration>/<start>/<end>')
def retarget(music_id, duration, start=True, end=True):
    pass


if __name__ == "__main__":
    app.run(port=8080)
