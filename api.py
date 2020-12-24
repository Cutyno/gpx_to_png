import flask
import gpx_to_png

app = flask.Flask(__name__)
app.config["DEBUG"] = True


@app.route('/')
@app.route("/home")
@app.route("/index")
def home():
    return "<h1>Distant Reading Archive</h1><p>This site is a prototype API for distant reading of science fiction novels.</p>"

@app.route("/api/v1/<map>/<int:z>/<int:x>/<int:y>")
def get_map_tile(map:str, z:int, x:int, y:int):
    map_cacher = gpx_to_png.MapCacher(map, "tmp")
    map_cacher.cache_tile(x, y, z)
    return flask.send_file(map_cacher.get_tile_filename(x, y, z), mimetype='image/png')

@app.errorhandler(404)
def page_not_found(e):
    return "<h1>404</h1><p>The resource could not be found.</p>", 404

app.run()