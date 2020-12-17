# -*- coding: utf-8 -*-

import sys
import math
import logging
import requests
import os
import gpxpy
from PIL import Image as pil_image
from PIL import ImageDraw as pil_draw
import glob

# Constance
osm_tile_res = 256
max_tile = 1
margin = 0.01

urls = {
    "toner": [
        "http://tile.stamen.com/toner/{z}/{x}/{y}.png",
        "http://a.tile.stamen.com/toner/{z}/{x}/{y}.png",
        "http://b.tile.stamen.com/toner/{z}/{x}/{y}.png",
        "http://c.tile.stamen.com/toner/{z}/{x}/{y}.png",
        "http://d.tile.stamen.com/toner/{z}/{x}/{y}.png"
    ],
    "terrain": [
        "http://tile.stamen.com/terrain/{z:n}/{x:n}/{y:n}.png",
        "http://a.tile.stamen.com/terrain/{z}/{x}/{y}.png",
        "http://b.tile.stamen.com/terrain/{z}/{x}/{y}.png",
        "http://c.tile.stamen.com/terrain/{z}/{x}/{y}.png",
        "http://d.tile.stamen.com/terrain/{z}/{x}/{y}.png"
    ],
    "watercolor": [
        "http://tile.stamen.com/watercolor/{z}/{x}/{y}.png",
        "http://a.tile.stamen.com/watercolor/{z}/{x}/{y}.png",
        "http://b.tile.stamen.com/watercolor/{z}/{x}/{y}.png",
        "http://c.tile.stamen.com/watercolor/{z}/{x}/{y}.png",
        "http://d.tile.stamen.com/watercolor/{z}/{x}/{y}.png"
    ],
    "osm": [
        "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png"
    ],
    "osm-de": [
        "https://a.tile.openstreetmap.de/{z}/{x}/{y}.png",
        "https://b.tile.openstreetmap.de/{z}/{x}/{y}.png",
        "https://c.tile.openstreetmap.de/{z}/{x}/{y}.png"
    ],
    "humanitarian": [
        "http://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
        "http://b.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png"
    ],
    "osm-fr": [
        "http://a.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png",
        "http://b.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png",
        "http://c.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png"
    ],
    "topo": [
        "https://a.tile.opentopomap.org/{z}/{x}/{y}.png",
        "https://b.tile.opentopomap.org/{z}/{x}/{y}.png",
        "https://c.tile.opentopomap.org/{z}/{x}/{y}.png"
    ]
}


def format_time(time_s):
    if not time_s:
        return 'n/a'
    minutes = math.floor(time_s / 60)
    hours = math.floor(minutes / 60)
    return '%s:%s:%s' % (str(int(hours)).zfill(2), str(int(minutes % 60)).zfill(2), str(int(time_s % 60)).zfill(2))


def osm_lat_lon_to_x_y_tile(lat_deg, lon_deg, zoom):
    """ Gets tile containing given coordinate at given zoom level """
    # taken from http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames, works for OSM maps
    lat_rad = math.radians(lat_deg)
    n = 2 ** zoom
    xtile = int((lon_deg + 180) / 360 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) +
                                (1 / math.cos(lat_rad))) / math.pi) / 2 * n)
    return (xtile, ytile)


def osm_get_auto_zoom_level(min_lat, max_lat, min_lon, max_lon, max_n_tiles):
    """ Gets zoom level which contains at maximum `max_n_tiles` """
    for z in range(0, 17):
        x1, y1 = osm_lat_lon_to_x_y_tile(min_lat, min_lon, z)
        x2, y2 = osm_lat_lon_to_x_y_tile(max_lat, max_lon, z)
        max_tiles = max(abs(x2 - x1), abs(y2 - y1))
        if (max_tiles > max_n_tiles):
            print("Max tiles: %d" % max_tiles)
            return z
    return 17


class MapCacher:
    """ Class for caching maps """

    def __init__(self, map: str, folder: str) -> None:
        self.map_name = map
        self.servers = urls[map].copy()
        self.root = folder

    def change_server(self, map: str) -> None:
        self.map_name = map
        self.servers = urls[map].copy()

    def get_tile_urls(self, x: int, y: int, z: int):
        remote = self.servers.copy()
        for i in range(len(remote)):
            remote[i] = remote[i].format(x=x, y=y, z=z)
        return remote

    def get_tile_filename(self, x: int, y: int, z: int) -> str:
        return self.root + r"/%s/%d/%d/%d.png" % (self.map_name, z, x, y)

    def cache_area(self, x_min, x_max, y_min, y_max, z) -> None:
        """ Downloads necessary tiles to cache """
        print("Caching tiles x1=%d y1=%d x2=%d y2=%d" %
              (x_min, y_min, x_max, y_max))
        for y in range(y_min, y_max + 1):
            for x in range(x_min, x_max + 1):
                self.cache_tile(x, y, z)

    def cache_tile(self, x, y, z) -> None:
        """ Downloads tile x,y,x into cache. Directories are automatically created, existing files are not retrieved. """
        src_urls = self.get_tile_urls(x, y, z)
        dst_filename = self.get_tile_filename(x, y, z)

        dst_dir = os.path.dirname(dst_filename)
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)
        if os.path.isfile(dst_filename):
            return
        data = None
        for i in range(len(src_urls)):
            print("Downloading from Mirror %d: %s ..." % (i, src_urls[i]))
            try:
                response = requests.get(src_urls[i])
                code = response.status_code
                if code == 200:
                    data = response.content
                    break
                else:
                    print("Error occurred! Response code: %d" % code)
            except:
                print("ERROR BY ACCESSING URL: %s" % src_urls[i])
        if data != None:
            f = open(dst_filename, "wb")
            f.write(data)
            f.close()


class MapCreator:
    """ Class for map drawing """

    def __init__(self, min_lat, max_lat, min_lon, max_lon, z):
        """ constructor """
        x1, y1 = osm_lat_lon_to_x_y_tile(min_lat, min_lon, z)
        x2, y2 = osm_lat_lon_to_x_y_tile(max_lat, max_lon, z)
        self.x1 = min(x1, x2)
        self.x2 = max(x1, x2)
        self.y1 = min(y1, y2)
        self.y2 = max(y1, y2)
        self.w = (self.x2 - self.x1 + 1) * osm_tile_res
        self.h = (self.y2 - self.y1 + 1) * osm_tile_res
        self.z = z
        print(self.w, self.h)

    def aspect_ratio(self, ratio_max, ratio_min):
        if (self.y2 - self.y1 + 1) / (self.x2 - self.x1 + 1) > ratio_max:
            self.x2 += 1
            if (self.y2 - self.y1 + 1) / (self.x2 - self.x1 + 1) > ratio_max:
                self.x1 -= 1
        elif (self.y2 - self.y1 + 1) / (self.x2 - self.x1 + 1) < ratio_min:
            self.y2 += 1
            if (self.y2 - self.y1 + 1) / (self.x2 - self.x1 + 1) < ratio_min:
                self.y1 -= 1
        self.w = (self.x2 - self.x1 + 1) * osm_tile_res
        self.h = (self.y2 - self.y1 + 1) * osm_tile_res
        print(self.w, self.h)

    def create_area_background(self, map_cacher: MapCacher):
        """ Creates background map from cached tiles """
        map_cacher.cache_area(self.x1, self.x2, self.y1, self.y2, self.z)
        self.dst_img = pil_image.new("RGB", (self.w, self.h))
        for y in range(self.y1, self.y2+1):
            for x in range(self.x1, self.x2+1):
                try:
                    src_img = pil_image.open(
                        map_cacher.get_tile_filename(x, y, self.z))
                except Exception as e:
                    print("Error processing file " +
                          map_cacher.get_tile_filename(x, y, self.z))
                    src_img = pil_image.open("error.png")
                dst_x = (x-self.x1)*osm_tile_res
                dst_y = (y-self.y1)*osm_tile_res
                self.dst_img.paste(src_img, (dst_x, dst_y))

    def lat_lon_to_image_xy(self, lat_deg, lon_deg):
        """ Internal. Converts lat, lon into dst_img coordinates in pixels """
        lat_rad = math.radians(lat_deg)
        n = 2.0 ** self.z
        xtile_frac = (lon_deg + 180) / 360 * n
        ytile_frac = (1.0 - math.log(math.tan(lat_rad) +
                                     (1 / math.cos(lat_rad))) / math.pi) / 2 * n
        img_x = int((xtile_frac-self.x1)*osm_tile_res)
        img_y = int((ytile_frac-self.y1)*osm_tile_res)
        return (img_x, img_y)

    def draw_track(self, gpx, color, thickness):
        """ Draw GPX track onto map """
        draw = pil_draw.Draw(self.dst_img)
        for track in gpx.tracks:
            for segment in track.segments:
                idx = 0
                x_from = 0
                y_from = 0
                for point in segment.points:
                    if (idx == 0):
                        x_from, y_from = self.lat_lon_to_image_xy(
                            point.latitude, point.longitude)
                    else:
                        x_to, y_to = self.lat_lon_to_image_xy(
                            point.latitude, point.longitude)
                        draw.line((x_from, y_from, x_to, y_to),
                                  color, thickness, "curve")
                        x_from = x_to
                        y_from = y_to
                    idx += 1

    def save_image(self, filename):
        print("Saving " + filename)
        self.dst_img.save(filename)


if (__name__ == '__main__'):
    """ Program entry point """

    gpx_files = []
    if(len(sys.argv) > 1):
        for i in range(1, len(sys.argv)):
            gpx_files.extend(glob.glob(r"{}/*.gpx".format(sys.argv[i])))
    else:
        gpx_files = glob.glob(r"*.gpx")

    if not gpx_files:
        print('No GPX files given')
        sys.exit(1)

    for gpx_file in gpx_files:
        try:
            gpx = gpxpy.parse(open(gpx_file))

            # Print some track stats
            print(
                '--------------------------------------------------------------------------------')
            print('  GPX file     : %s' % gpx_file)
            start_time, end_time = gpx.get_time_bounds()
            print('  Started       : %s' % start_time)
            print('  Ended         : %s' % end_time)
            print('  Length        : %2.2fkm' % (gpx.length_3d() / 1000.))
            moving_time, stopped_time, moving_distance, stopped_distance, max_speed = gpx.get_moving_data()
            print('  Moving time   : %s' % format_time(moving_time))
            print('  Stopped time  : %s' % format_time(stopped_time))
            print('  Max speed     : %2.2fm/s = %2.2fkm/h' %
                  (max_speed, max_speed * 60 ** 2 / 1000))
            uphill, downhill = gpx.get_uphill_downhill()
            print('  Total uphill  : %4.0fm' % uphill)
            print('  Total downhill: %4.0fm' % downhill)
            min_lat, max_lat, min_lon, max_lon = gpx.get_bounds()
            print("  Bounds        : [%1.4f,%1.4f,%1.4f,%1.4f]" % (
                min_lat, max_lat, min_lon, max_lon))
            z = osm_get_auto_zoom_level(
                min_lat, max_lat, min_lon, max_lon, max_tile)
            print("  Zoom Level    : %d" % z)

            # Cache the map
            map_cacher = MapCacher("terrain", "tmp")

            # Create the map
            map_creator = MapCreator(
                min_lat-margin, max_lat+margin, min_lon-margin, max_lon+margin, z)
            map_creator.aspect_ratio(2, 1.5)
            map_creator.create_area_background(map_cacher)
            map_creator.draw_track(gpx, (255, 0, 0), 4)
            map_creator.save_image(gpx_file[:-4] + '-map.png')

        except Exception as e:
            logging.exception(e)
            print('Error processing %s' % gpx_file)
            sys.exit(1)
