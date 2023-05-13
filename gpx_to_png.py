# -*- coding: utf-8 -*-
import sys
import math
import logging
from typing import IO, TypeVar, Union, Final, Tuple
import requests
import os
import gpxpy
from PIL import Image, ImageDraw, ImageCms
import glob
import yaml

error_count: int = 0
# Constants
osm_tile_res: Final = 256
server_file: Final = "server.yaml"
tile_cache: Final = "tmp"
# Settings
default_max_tile: int = 2
default_margin: float = 0.01
# Common aspect ratios
# A4    1.59
# 16:9  0.5625
default_aspect_ratio: float = 1.59
default_color_low: Tuple[int, int, int, int] = (4, 236, 240, 204)
default_color_high: Tuple[int, int, int, int] = (245, 23, 32, 204)
default_color_back: Tuple[int, int, int] = (255, 255, 255)
default_track_thickness: int = 7
default_background_thickness: int = 10
default_map: str = "terrain"


def format_time(time_s: float) -> str:
    if not time_s:
        return 'n/a'
    minutes: int = math.floor(time_s / 60)
    hours: int = math.floor(minutes / 60)
    return f"{str(int(hours)).zfill(2)}:{str(int(minutes % 60)).zfill(2)}:{str(int(time_s % 60)).zfill(2)}"


def osm_lat_lon_to_x_y_tile(lat_deg: float, lon_deg: float, zoom: int) -> (float, float):
    """ Gets tile containing given coordinate at given zoom level """
    # taken from http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames,
    # works for OSM maps
    lat_rad: float = math.radians(lat_deg)
    n: int = 2 ** zoom
    xtile: float = (lon_deg + 180) / 360 * n
    ytile: float = (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2 * n
    return (xtile, ytile)


def osm_get_auto_zoom_level(min_lat: float, max_lat: float, min_lon: float, max_lon: float, max_n_tiles: int) -> int:
    """ Gets zoom level which contains at maximum `max_n_tiles` """
    for z in range(0, 17):
        x1, y1 = osm_lat_lon_to_x_y_tile(min_lat, min_lon, z)
        x2, y2 = osm_lat_lon_to_x_y_tile(max_lat, max_lon, z)
        max_tiles = max(abs(x2 - x1), abs(y2 - y1))
        if (max_tiles > max_n_tiles):
            print(f"Max tiles: {max_tiles}")
            return z
    return 17


class GpxObj:
    def __init__(self, xml: Union[TypeVar("AnyStr"), IO[str]], max_tile: int = default_max_tile) -> None:
        self.gpx = gpxpy.parse(xml)
        self.min_lat, self.max_lat, self.min_lon, self.max_lon = self.gpx.get_bounds()
        self.min_ele, self.max_ele = self.gpx.get_elevation_extremes()
        self.z = osm_get_auto_zoom_level(self.min_lat, self.max_lat, self.min_lon, self.max_lon, max_tile)

    def stats(self) -> str:
        result = '--------------------------------------------------------------------------------\n'
        result += '  GPX file\n'
        start_time, end_time = self.gpx.get_time_bounds()
        result += f'  Started       : {start_time}\n'
        result += f'  Ended         : {end_time}\n'
        result += f'  Length        : {(self.gpx.length_3d() / 1000.0): 2.2f}km\n'
        moving_time, stopped_time, moving_distance, stopped_distance, max_speed = self.gpx.get_moving_data()
        result += f'  Moving time   : {format_time(moving_time)}\n'
        result += f'  Stopped time  : {format_time(stopped_time)}\n'
        result += f'  Max speed     : {max_speed: 2.2f}m/s = {(max_speed * 60 ** 2 / 1000): 2.2f}km/h'
        uphill, downhill = self.gpx.get_uphill_downhill()
        result += f'  Total uphill  : {uphill: 4.0f}m\n'
        result += f'  Total downhill: {downhill: 4.0f}m\n'
        result += f'  Bounds        : [{self.min_lat: 1.4f},{self.max_lat: 1.4f},{self.min_lon: 1.4f},{self.max_lon: 1.4f}]\n'
        result += f'  Elev. Bounds  : [{self.min_ele: 1.4f},{self.max_ele: 1.4f}]\n'
        result += f'  Zoom Level    : {self.z}'
        return result


class MapCacher:
    """ Class for caching maps """

    def __init__(self, _map: str, folder: str) -> None:
        self.map_name = _map
        f = open(server_file, 'r')
        # Loader=yaml,BaseLoader Only loads the most basic YAML.
        # All scalars are loaded as strings.
        url = yaml.load(f, Loader=yaml.BaseLoader)
        try:
            self.servers = url[_map]
        except KeyError:
            self.servers = url["osm"]
        f.close()
        self.root = folder

    def change_server(self, _map: str) -> None:
        self.map_name = _map
        f = open(server_file, 'r')
        # Loader=yaml,BaseLoader Only loads the most basic YAML.
        # All scalars are loaded as strings.
        url = yaml.load(f, Loader=yaml.BaseLoader)
        try:
            self.servers = url[_map]
        except KeyError:
            self.servers = url["osm"]
        f.close()

    def get_tile_urls(self, x: int, y: int, z: int) -> str:
        remote = self.servers.copy()
        for i in range(len(remote)):
            remote[i] = remote[i].format(x=x, y=y, z=z)
        return remote

    def get_tile_filename(self, x: int, y: int, z: int) -> str:
        return self.root + r"/%s/%d/%d/%d.png" % (self.map_name, z, x, y)

    def cache_area(self, x_min, x_max, y_min, y_max, z) -> None:
        """ Downloads necessary tiles to cache """
        print(f"Caching tiles x1={x_min} y1={y_min} x2={x_max} y2={y_max}")
        for y in range(y_min, y_max + 1):
            for x in range(x_min, x_max + 1):
                self.cache_tile(x, y, z)

    def cache_tile(self, x: int, y: int, z: int) -> None:
        """
        Downloads tile x,y,x into cache.
        Directories are automatically created, existing files are not retrieved.
        """
        src_urls = self.get_tile_urls(x, y, z)
        dst_filename = self.get_tile_filename(x, y, z)

        dst_dir = os.path.dirname(dst_filename)
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir, exist_ok=True)
        if os.path.isfile(dst_filename):
            return
        data = None
        for i in range(len(src_urls)):
            print(f"Downloading from Mirror {i}: {src_urls[i]} ...")
            try:
                response = requests.get(src_urls[i])
                code = response.status_code
                if code == 200:
                    data = response.content
                    break
                else:
                    print(f"Error occurred! Response code: {code}")
            except Exception() as e:
                print(f"ERROR BY ACESSING URL: {src_urls[i]} [{e}]")
        if data is not None:
            f = open(dst_filename, "wb")
            f.write(data)
            f.close()


class MapCreator:
    """ Class for map drawing """

    def __init__(self,
                 min_lat: float,
                 max_lat: float,
                 min_lon: float,
                 max_lon: float,
                 z: int,
                 min_ele: float = 0,
                 max_ele: float = 0,
                 max_tile: int = default_max_tile,
                 margin: float = 0) -> None:
        """ constructor """
        x1, y1 = osm_lat_lon_to_x_y_tile(min_lat - margin, min_lon - margin, z)
        x2, y2 = osm_lat_lon_to_x_y_tile(max_lat + margin, max_lon + margin, z)
        self.dx = abs(x2 - x1)
        self.x1 = int(min(x1, x2)) - max_tile
        self.x2 = int(max(x1, x2)) + max_tile
        self.px = min(x1, x2) - self.x1
        self.dy = abs(y2 - y1)
        self.py = min(y1, y2)
        self.y1 = int(min(y1, y2)) - max_tile
        self.y2 = int(max(y1, y2)) + max_tile
        self.py = min(y1, y2) - self.y1
        self.e = min(min_ele, max_ele)
        self.de = max(min_ele, max_ele) - self.e
        self.w = (self.x2 - self.x1 + 1) * osm_tile_res
        self.h = (self.y2 - self.y1 + 1) * osm_tile_res
        self.z = z
        print(self.w, self.h)

    @classmethod
    def from_gpx(cls, gpx: GpxObj, _margin: int = 0, max_tile: int = default_max_tile):
        return cls(gpx.min_lat, gpx.max_lat, gpx.min_lon, gpx.max_lon, gpx.z, gpx.min_ele, gpx.max_ele, max_tile, _margin)

    def create_area_background(self, map_cacher: MapCacher) -> None:
        """ Creates background map from cached tiles """
        map_cacher.cache_area(self.x1, self.x2, self.y1, self.y2, self.z)
        self.dst_img = Image.new("RGB", (self.w, self.h))
        for y in range(self.y1, self.y2+1):
            for x in range(self.x1, self.x2+1):
                try:
                    src_img = Image.open(
                        map_cacher.get_tile_filename(x, y, self.z))
                except Exception as e:
                    print(f"Error processing file {map_cacher.get_tile_filename(x, y, self.z)} [{e}]")
                    src_img = Image.open("error.png")
                dst_x = (x - self.x1) * osm_tile_res
                dst_y = (y - self.y1) * osm_tile_res
                self.dst_img.paste(src_img, (dst_x, dst_y))

    def lat_lon_to_image_xy(self, lat_deg: float, lon_deg: float) -> (int, int):
        """ Internal. Converts lat, lon into dst_img coordinates in pixels """
        lat_rad = math.radians(lat_deg)
        n = 2.0 ** self.z
        xtile_frac = (lon_deg + 180) / 360 * n
        ytile_frac = (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2 * n
        img_x = int((xtile_frac-self.x1)*osm_tile_res)
        img_y = int((ytile_frac-self.y1)*osm_tile_res)
        return (img_x, img_y)

    def draw_track(self, gpx, color_array, thickness) -> None:
        """ Draw GPX track onto map """
        draw = ImageDraw.Draw(self.dst_img)
        for track in gpx.tracks:
            for segment in track.segments:
                idx = 0
                points = []
                z_val = []
                for point in segment.points:
                    if (idx == 0):
                        x, y = self.lat_lon_to_image_xy(
                            point.latitude, point.longitude)
                        points = [(x, y)]
                        z_val = [point.elevation]
                    else:
                        x, y = self.lat_lon_to_image_xy(
                            point.latitude, point.longitude)
                        points.append((x, y))
                        z_val.append(point.elevation)
                        if len(points) > 3:
                            points.pop(0)
                        if len(z_val) > 3:
                            z_val.pop(0)
                        z = ((z_val[0] + z_val[-1]) / 2) - self.e
                        color_idx = max(min(z / self.de, 1), 0)
                        color0 = int((color_array[0][0] * (1 - color_idx)) + (color_array[1][0] * color_idx))
                        color1 = int((color_array[0][1] * (1 - color_idx)) + (color_array[1][1] * color_idx))
                        color2 = int((color_array[0][2] * (1 - color_idx)) + (color_array[1][2] * color_idx))
                        color = (color0, color1, color2)
                        draw.line(points, color, thickness, "curve")
                    idx += 1

    def draw_track_back(self, gpx, color, thickness) -> None:
        """ Draw GPX background onto map """
        draw = ImageDraw.Draw(self.dst_img)
        points = []
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    x, y = self.lat_lon_to_image_xy(point.latitude, point.longitude)
                    points.append((x, y))
        draw.line(points, color, thickness, "curve")
        draw.ellipse(
            [
                points[0][0] - thickness,
                points[0][1] - thickness,
                points[0][0] + thickness,
                points[0][1] + thickness
            ], fill=color)
        draw.ellipse(
            [
                points[-1][0] - thickness,
                points[-1][1] - thickness,
                points[-1][0] + thickness,
                points[-1][1] + thickness
            ], fill=color)

    def crop_image(self, aspect) -> None:
        # aspect = (self.y2 - self.y1 + 1) / (self.x2 - self.x1 + 1)
        x1 = abs(self.px)
        y1 = abs(self.py)
        x2 = x1 + self.dx
        y2 = y1 + self.dy
        dy = aspect * self.dx
        dx = self.dy / aspect
        print(f"dy1 = {self.dy: 1.4f} dy2 = {dy: 1.4f} dx1 = {self.dx: 1.4f} dx2 = {dx: 1.4f}")
        if dy > self.dy:
            dy = (dy - self.dy) / 2
            y1 -= dy
            y2 += dy
        elif dx > self.dx:
            dx = (dx - self.dx) / 2
            x1 -= dx
            x2 += dx
        else:
            print("can't crop img")
        print(f" crop to x1 = {x1: 1.4f} y1 = {y1: 1.4f} x2 = {x2: 1.4f} y2 = {y2: 1.4f}")
        self.dst_img = self.dst_img.crop((x1 * osm_tile_res, y1 * osm_tile_res, x2 * osm_tile_res, y2 * osm_tile_res))

    def save_image(self, filename: str) -> None:
        filename += ".png"
        print("Saving " + filename)
        self.dst_img.save(filename)

    def save_print_image(self, filename: str) -> None:
        filename += ".jpg"
        print("Saving CMYK image " + filename)
        img = ImageCms.profileToProfile(
            self.dst_img,
            '/Library/Application Support/Adobe/Color/Profiles/AdobeRGB1998.icc',
            '/Library/Application Support/Adobe/Color/Profiles/CoatedFOGRA39.icc',
            renderingIntent=0,
            outputMode='CMYK'
        )
        img.save(filename)


if __name__ == '__main__':
    """ Program entry point """

    # Search for gpx files
    gpx_files = []
    if len(sys.argv) > 1:
        for i in range(1, len(sys.argv)):
            gpx_files.extend(glob.glob(r"{}/*.gpx".format(sys.argv[i])))
    else:
        gpx_files = glob.glob(r"*.gpx")

    # Check gpx files
    if not gpx_files:
        print('No GPX files given')
        sys.exit(1)

    for i in range(len(gpx_files)):

        # Print progress bar
        percentage = i / len(gpx_files) * 100
        print(f"progress: |{int(percentage/2)*'='}>{int(50-percentage/2)*' '}| [{percentage}%]")

        # set default values
        max_tile = default_max_tile
        margin = default_margin
        aspect_ratio = default_aspect_ratio
        color_low = default_color_low
        color_high = default_color_high
        color_back = default_color_back
        track_thickness = default_track_thickness
        background_thickness = default_background_thickness
        map = default_map

        try:
            # load custom config
            config_path = gpx_files[i][:-3] + "yaml"
            print(config_path)
            if os.path.exists(config_path):
                config = yaml.load(open(config_path), Loader=yaml.BaseLoader)
                print(config)
                if 'max_tile' in config:
                    max_tile = int(config['max_tile'])
                if 'margin' in config:
                    margin = float(config['margin'])
                if 'aspect_ratio' in config:
                    aspect_ratio = float(config['aspect_ratio'])
                if 'line_thickness' in config:
                    track_thickness = int(config['line_thickness'])
                if 'background_thickness' in config:
                    background_thickness = int(config['background_thickness'])
                if 'map' in config:
                    map = config['map']
            else:
                print("no custom config")

            # Load the Gpx file
            gpx = GpxObj(open(gpx_files[i]), max_tile)

            # Print some track stats
            print(gpx.stats())

            # Cache the map
            map_cacher = MapCacher(map, tile_cache)

            # Create the map
            map_creator = MapCreator.from_gpx(gpx, margin)
            map_creator.create_area_background(map_cacher)

            # Draw background for better visibility
            map_creator.draw_track_back(gpx.gpx, color_back, background_thickness)

            # draw track
            map_creator.draw_track(gpx.gpx, (color_low, color_high), track_thickness)

            # cut img to desired dimensions
            map_creator.crop_image(aspect_ratio)

            # export img
            # map_creator.save_print_image(gpx_files[i][:-4] + '-map')
            map_creator.save_image(gpx_files[i][:-4] + '-map')

        except Exception as e:
            logging.exception(e)
            error_count += 1
            print(f'Error processing {gpx_files[i]} [{e}]')

        print(f"Total Error: {error_count}")
