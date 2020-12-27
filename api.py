import flask
from flask.globals import request
from flask.helpers import url_for
from werkzeug.utils import redirect
import gpx_to_png
import io
import yaml

app = flask.Flask(__name__)
app.config["DEBUG"] = True


@app.route("/api/v1/tile/<map>/<int:z>/<int:x>/<int:y>", methods=['GET'])
def get_map_tile(map: str, z: int, x: int, y: int):
    map_cacher = gpx_to_png.MapCacher(map, "tmp")
    map_cacher.cache_tile(x, y, z)
    return flask.send_file(map_cacher.get_tile_filename(x, y, z), attachment_filename='%d.png' % y, mimetype='image/png', as_attachment=True)


@app.route("/api/v1/map/<map>/<int:z>/<float:lat_min>/<float:lat_max>/<float:lon_min>/<float:lon_max>", methods=['GET'])
def get_map_background(map: str, z: int, lat_min: float, lat_max: float, lon_min: float, lon_max: float):
    # Cache the map
    map_cacher = gpx_to_png.MapCacher(map, "tmp")
    # Create the map
    map_creator = gpx_to_png.MapCreator(lat_min, lat_max, lon_min, lon_max, z)
    map_creator.create_area_background(map_cacher)
    f = io.BytesIO()
    map_creator.dst_img.save(f, format='PNG')
    f.seek(0)
    return flask.send_file(f, attachment_filename='map.png', mimetype='image/png', as_attachment=True)


@app.route("/api/v1/gpx/<map>", methods=['POST', 'GET'])
def get_gpx_map(map):
    if flask.request.method == 'POST':
        # check if the post request has the file part
        if 'gpx' not in request.files:
            return redirect(url_for("page_not_found"))
        gpx_file = request.files['gpx']
        # if user does not select file, browser also
        # submit an empty part without filename
        if gpx_file.filename == '':
            return redirect(url_for("page_not_found"))
        if gpx_file and gpx_file.filename.rsplit('.', 1)[1].lower() == "gpx":
            try:
                gpx = gpx_to_png.GpxObj(gpx_file)
                # Print some track stats
                print(gpx.stats())
                # Cache the map
                map_cacher = gpx_to_png.MapCacher(map, "tmp")
                # Create the map
                map_creator = gpx_to_png.MapCreator.from_gpx(
                    gpx, gpx_to_png.margin)
                map_creator.create_area_background(map_cacher)
                map_creator.draw_track(gpx.gpx, (255, 0, 0), 4)
                f = io.BytesIO()
                map_creator.dst_img.save(f, format='PNG')
                f.seek(0)
                return flask.send_file(f, attachment_filename=gpx_file.filename + '-map.png', mimetype='image/png', as_attachment=True)

            except Exception as e:
                gpx_to_png.logging.exception(e)
                print('Error processing %s' % gpx_file)
                return "<h1>500</h1><p>The process could not be finished.</p>", 500
    return "<h1>404</h1><p>The resource could not be found.</p>", 404


@app.route('/')
@app.route("/home")
@app.route("/index")
@app.route("/api/v1/gpx", methods=['GET', 'POST'])
def set_gpx_map():
    if request.method == 'POST':
        if request.form["map"] is not None:
            print(request.form["map"])
            return redirect("/api/v1/gpx/" + request.form["map"], code=307)
        return redirect(url_for("page_not_found"))
    page = '''<!doctype html>
    <title>Upload new gpx File</title>
    <h1>Upload new gpx File</h1>
    <form method=post enctype=multipart/form-data action="/api/v1/gpx">
      <input type=file name=gpx>
      <select name=map>
    '''
    f = open("server.yaml", 'r')
    url = yaml.load(f, Loader=yaml.BaseLoader)
    for server in url.keys():
        page += "<option value=" + server + ">" + server + "</option>\n"
    page += '''</select>
    <br><br>
    <input type=submit value=Upload>
    </form>
    '''
    return page


@app.errorhandler(404)
def page_not_found(e):
    return "<h1>404</h1><p>The resource could not be found.</p>", 404

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int("80"), debug=True)
