import flask
from flask.globals import request
from flask.helpers import url_for
from werkzeug.utils import redirect
import gpx_to_png
import io
import yaml

app = flask.Flask(__name__)
app.config["DEBUG"] = False

def hex_to_rbg(hex_color):
    hex = str(hex_color)
    return tuple(int(hex[i:i+2], 16) for i in (1, 3, 5))

@app.route("/api/v1/tile/<map>/<int:z>/<int:x>/<int:y>", methods=['GET'])
def get_map_tile(map: str, z: int, x: int, y: int):
    map_cacher = gpx_to_png.MapCacher(map, "tmp")
    map_cacher.cache_tile(x, y, z)
    return flask.send_file(map_cacher.get_tile_filename(x, y, z), download_name='%d.png' % y, mimetype='image/png', as_attachment=True)


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
    return flask.send_file(f, download_name='map.png', mimetype='image/png', as_attachment=True)


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
        max_tile = gpx_to_png.default_max_tile
        if 'max_tile' in request.form:
            max_tile = int(request.form.get('max_tile'))
        margin = gpx_to_png.default_margin
        if 'margin' in request.form:
            margin = float(request.form.get('margin'))
        aspect_ratio = gpx_to_png.default_aspect_ratio
        if 'aspect_ratio' in request.form:
            aspect_ratio = float(request.form.get('aspect_ratio'))
        color_low = gpx_to_png.default_color_low
        if 'track_color_low' in request.form:
            color_low = hex_to_rbg(request.form.get('track_color_low'))
        color_high = gpx_to_png.default_color_high
        if 'track_color_high' in request.form:
            color_high = hex_to_rbg(request.form.get('track_color_high'))
        color_back = gpx_to_png.default_color_back
        if 'back_color' in request.form:
            color_back = hex_to_rbg(request.form.get('back_color'))
        track_thickness = gpx_to_png.default_track_thickness
        if 'line_thickness' in request.form:
            track_thickness = int(request.form.get('line_thickness'))
        background_thickness = gpx_to_png.default_track_thickness
        if 'background_thickness' in request.form:
            background_thickness = int(request.form.get('background_thickness'))
        map = "terrain"
        if 'map' in request.form:
            map = request.form.get('map')
        if gpx_file and gpx_file.filename.rsplit('.', 1)[1].lower() == "gpx":
            try:
                gpx = gpx_to_png.GpxObj(gpx_file, max_tile)
                # Print some track stats
                print(gpx.stats())
                # Cache the map
                map_cacher = gpx_to_png.MapCacher(map, gpx_to_png.tile_cache)
                # Create the map
                map_creator = gpx_to_png.MapCreator.from_gpx(gpx, margin)
                map_creator.create_area_background(map_cacher)
                map_creator.draw_track_back(gpx.gpx, color_back, background_thickness)
                map_creator.draw_track(gpx.gpx, (color_low, color_high), track_thickness)
                # cut img to desired dimensions
                map_creator.crop_image(aspect_ratio)
                f = io.BytesIO()
                map_creator.dst_img.save(f, format='PNG')
                f.seek(0)
                return flask.send_file(f, download_name=gpx_file.filename + '-map.png', mimetype='image/png', as_attachment=True)

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
      File <input type=file name=gpx><br>
      Map <select name=map >
    '''
    f = open("server.yaml", 'r')
    url = yaml.load(f, Loader=yaml.BaseLoader)
    for server in url.keys():
        page += "<option value=" + server
        if server == 'osm':
            page += ' selected'
        page += ">" + server + "</option>\n"
    page += '''</select><br>
      Maximum tiles <input type=number name=max_tile min=1 max=5 step=1 value=1><br>
      Margin <input type=number name=margin min=0 max=1 step=0.01 value=0.1><br>
      Aspect ratio <input type=number name=aspect_ratio min=0.5 max=2 step=0.01 value=1><br>
      Background Color <input type=color name=back_color value=#ffffff><br>
      Track Color (highes point) <input type=color name=track_color_high value=#ff0000>
      (lowest point) <input type=color name=track_color_low value=#ff0000><br>
      Shadow thickness <input type=number name=background_thickness min=3 max=22 step=2 value=7><br>
      Line thickness <input type=number name=line_thickness min=1 max=20 step=1 value=5><br>
    <br><br>
    <input type=submit value=Upload>
    </form>
    '''
    return page


@app.errorhandler(404)
def page_not_found(e):
    return "<h1>404</h1><p>The resource could not be found.</p>", 404

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int("80"), debug=False)
