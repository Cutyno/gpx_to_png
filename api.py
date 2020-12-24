import flask
import gpx_to_png
import io

app = flask.Flask(__name__)
app.config["DEBUG"] = True


@app.route('/')
@app.route("/home")
@app.route("/index")
def home():
    return "<h1>Distant Reading Archive</h1><p>This site is a prototype API for distant reading of science fiction novels.</p>"

@app.route("/api/v1/tile/<map>/<int:z>/<int:x>/<int:y>", methods=['GET'])
def get_map_tile(map:str, z:int, x:int, y:int):
    map_cacher = gpx_to_png.MapCacher(map, "tmp")
    map_cacher.cache_tile(x, y, z)
    return flask.send_file(map_cacher.get_tile_filename(x, y, z), mimetype='image/png')

@app.route("/api/v1/map/<map>/<int:z>/<float:lat_min>/<float:lat_max>/<float:lon_min>/<float:lon_max>", methods=['GET'])
def get_map_background(map:str, z:int, lat_min:float, lat_max:float, lon_min:float, lon_max:float):
    # Cache the map
    map_cacher = gpx_to_png.MapCacher(map, "tmp")
    # Create the map
    map_creator = gpx_to_png.MapCreator(lat_min, lat_max, lon_min, lon_max, z)
    map_creator.create_area_background(map_cacher)
    f = io.BytesIO()
    map_creator.dst_img.save(f, format='PNG')
    f.seek(0)
    return flask.send_file(f, mimetype='image/png')

@app.errorhandler(404)
def page_not_found(e):
    return "<h1>404</h1><p>The resource could not be found.</p>", 404

app.run()