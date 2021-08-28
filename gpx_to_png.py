# -*- coding: utf-8 -*-
import sys
import math
import logging
from typing import IO, TypeVar, Union
import requests
import os
import gpxpy
from PIL import Image as pil_image
from PIL import ImageDraw as pil_draw
import glob
import yaml

# Constance
osm_tile_res = 256
max_tile = 1
margin = 0.01
aspect_ratio = 2
color_low = (4, 236, 240)
color_high = (245, 23, 32)
color_back = (255, 255, 255)
server_file = "server.yaml"
tile_cache = "tmp"


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
    xtile = (lon_deg + 180) / 360 * n
    ytile = (1.0 - math.log(math.tan(lat_rad) +
                                (1 / math.cos(lat_rad))) / math.pi) / 2 * n
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
        f = open(server_file, 'r')
        url = yaml.load(f, Loader=yaml.BaseLoader) # Loader=yaml,BaseLoader Only loads the most basic YAML. All scalars are loaded as strings.
        try:
            self.servers = url[map]
        except KeyError:
            self.servers = url["osm"]
        f.close()
        self.root = folder

    def change_server(self, map: str) -> None:
        self.map_name = map
        f = open(server_file, 'r')
        url = yaml.load(f, Loader=yaml.BaseLoader) # Loader=yaml,BaseLoader Only loads the most basic YAML. All scalars are loaded as strings.
        try:
            self.servers = url[map]
        except KeyError:
            self.servers = url["osm"]
        f.close()

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

    def __init__(self, min_lat, max_lat, min_lon, max_lon, min_ele, max_ele, z) -> None:
        """ constructor """
        x1, y1 = osm_lat_lon_to_x_y_tile(min_lat, min_lon, z)
        x2, y2 = osm_lat_lon_to_x_y_tile(max_lat, max_lon, z)
        self.dx = abs(x2 - x1)
        self.x1 = int(min(x1, x2))
        self.x2 = int(max(x1, x2))
        self.px = min(x1, x2) - self.x1
        self.dy = abs(y2 - y1)
        self.py = min(y1, y2)
        self.y1 = int(min(y1, y2))
        self.y2 = int(max(y1, y2))
        self.py = min(y1, y2) - self.y1
        self.e = min(min_ele, max_ele)
        self.de = max(min_ele, max_ele) - self.e
        self.w = (self.x2 - self.x1 + 1) * osm_tile_res
        self.h = (self.y2 - self.y1 + 1) * osm_tile_res
        self.z = z
        print(self.w, self.h)

    @classmethod
    def from_gpx(cls, gpx, margin):
        return cls(gpx.min_lat-margin, gpx.max_lat+margin, gpx.min_lon-margin, gpx.max_lon+margin, gpx.min_ele, gpx.max_ele, gpx.z)

    def aspect_ratio(self, ratio_max, ratio_min):
        if (self.y2 - self.y1 + 1) / (self.x2 - self.x1 + 1) > ratio_max:
            self.x2 += 1
            if (self.y2 - self.y1 + 1) / (self.x2 - self.x1 + 1) > ratio_max:
                self.x1 -= 1
                self.px += 1
        elif (self.y2 - self.y1 + 1) / (self.x2 - self.x1 + 1) < ratio_min:
            self.y2 += 1
            if (self.y2 - self.y1 + 1) / (self.x2 - self.x1 + 1) < ratio_min:
                self.y1 -= 1
                self.py += 1
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

    def draw_track(self, gpx, color_array, thickness):
        """ Draw GPX track onto map """
        draw = pil_draw.Draw(self.dst_img)
        for track in gpx.tracks:
            for segment in track.segments:
                idx = 0
                x_from = 0
                y_from = 0
                z_from = 0
                for point in segment.points:
                    if (idx == 0):
                        x_from, y_from = self.lat_lon_to_image_xy(
                            point.latitude, point.longitude)
                        z_from = point.elevation
                    else:
                        x_to, y_to = self.lat_lon_to_image_xy(
                            point.latitude, point.longitude)
                        z_to = point.elevation
                        z = ((z_from + z_to) / 2) - self.e
                        color_idx = max(min(z / self.de, 1), 0)
                        color0 = int((color_array[0][0] * (1 - color_idx)) + (color_array[1][0] * color_idx))
                        color1 = int((color_array[0][1] * (1 - color_idx)) + (color_array[1][1] * color_idx))
                        color2 = int((color_array[0][2] * (1 - color_idx)) + (color_array[1][2] * color_idx))
                        color = (color0, color1, color2)
                        draw.line((x_from, y_from, x_to, y_to),
                                  color, thickness, "curve")
                        x_from = x_to
                        y_from = y_to
                        z_from = z_to
                    idx += 1

    def draw_track_back(self, gpx, color, thickness):
        """ Draw GPX background onto map """
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
                        draw.ellipse(
                            [
                                x_from - thickness,
                                y_from - thickness,
                                x_from + thickness,
                                y_from + thickness
                            ], fill=color_back)
                    else:
                        x_to, y_to = self.lat_lon_to_image_xy(
                            point.latitude, point.longitude)
                        draw.line((x_from, y_from, x_to, y_to),
                                  color, thickness, "curve")
                        x_from = x_to
                        y_from = y_to
                    idx += 1
                draw.ellipse(
                    [
                        x_from - thickness,
                        y_from - thickness,
                        x_from + thickness,
                        y_from + thickness
                    ], fill=color_back)

    def crop_image(self, aspect):
        # aspect = (self.y2 - self.y1 + 1) / (self.x2 - self.x1 + 1)
        x1 = abs(self.px)
        y1 = abs(self.py)
        x2 = x1 + self.dx
        y2 = y1 + self.dy
        dy = aspect * self.dx
        dx = self.dy / aspect
        print("dy1 = %1.4f dy2 = %1.4f dx1 = %1.4f dx2 = %1.4f" % (self.dy, dy, self.dx, dx))
        if(dy > self.dy):
            dy = (dy - self.dy) / 2
            y1 -= dy
            y2 += dy
        elif(dx > self.dx):
            dx = (dx - self.dx) / 2
            x1 -= dx
            x2 += dx
        else:
            print("can't crop img")
        print(" crop to x1 = %1.4f y1 = %1.4f x2 = %1.4f y2 = %1.4f" % (x1, y1, x2, y2))
        self.dst_img = self.dst_img.crop((x1 * osm_tile_res, y1 * osm_tile_res, x2 * osm_tile_res, y2 * osm_tile_res))


    def save_image(self, filename):
        print("Saving " + filename)
        self.dst_img.save(filename)

class GpxObj:
    def __init__(self, xml: Union[TypeVar("AnyStr"), IO[str]]) -> None:
        self.gpx = gpxpy.parse(xml)
        self.min_lat, self.max_lat, self.min_lon, self.max_lon = self.gpx.get_bounds()
        self.min_ele, self.max_ele = self.gpx.get_elevation_extremes()
        self.z = osm_get_auto_zoom_level(self.min_lat, self.max_lat, self.min_lon, self.max_lon, max_tile)
        
        
        
    def stats(self) -> str:
        result = '--------------------------------------------------------------------------------\n'
        result += '  GPX file\n'
        start_time, end_time = self.gpx.get_time_bounds()
        result += '  Started       : %s\n' % start_time
        result += '  Ended         : %s\n' % end_time
        result += '  Length        : %2.2fkm\n' % (self.gpx.length_3d() / 1000.)
        moving_time, stopped_time, moving_distance, stopped_distance, max_speed = self.gpx.get_moving_data()
        result += '  Moving time   : %s\n' % format_time(moving_time)
        result += '  Stopped time  : %s\n' % format_time(stopped_time)
        result += '  Max speed     : %2.2fm/s = %2.2fkm/h' % (max_speed, max_speed * 60 ** 2 / 1000)
        uphill, downhill = self.gpx.get_uphill_downhill()
        result += '  Total uphill  : %4.0fm\n' % uphill
        result += '  Total downhill: %4.0fm\n' % downhill
        result += '  Bounds        : [%1.4f,%1.4f,%1.4f,%1.4f]\n' % (self.min_lat, self.max_lat, self.min_lon, self.max_lon)
        result += '  Elev. Bounds  : [%1.4f,%1.4f]\n' % (self.min_ele, self.max_ele)
        result += '  Zoom Level    : %d' % self.z
        return result


def create_png(gpx_file, map):
    try:
        # Load the Gpx file
        gpx = GpxObj(open(gpx_file))

        # Print some track stats
        print(gpx.stats())

        # Cache the map
        map_cacher = MapCacher(map, tile_cache)

        # Create the map
        map_creator = MapCreator.from_gpx(gpx, margin)
        map_creator.aspect_ratio(2, 1.5)
        map_creator.create_area_background(map_cacher)
        map_creator.draw_track_back(gpx.gpx, color_back, 6)
        map_creator.draw_track(gpx.gpx, (color_low, color_high), 4)
        map_creator.crop_image(aspect_ratio)
        map_creator.save_image(gpx_file[:-4] + '-map.png')

    except Exception as e:
        logging.exception(e)
        print('Error processing %s' % gpx_file)

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
    for i in range(len(gpx_files)):
        percentage = i / len(gpx_files) * 100
        print("progress: |%s>%s| [%d%%]" % (int(percentage/2)*"=", int(50-percentage/2)*" ", percentage))
        create_png(gpx_files[i], "terrain")
