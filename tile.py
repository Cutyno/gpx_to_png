from typing import Final
import yaml
import math
import os
import requests
from PIL import Image, ImageDraw

# Constants
osm_tile_res: Final = 256
server_file: Final = "server.yaml"


class TileCacher:
    """ Class for caching tiles """

    def __init__(self, _map: str, folder: str) -> None:
        self.change_server(_map)
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
                print(f"ERROR BY ACCESSING URL: {src_urls[i]} [{e}]")
        if data is not None:
            f = open(dst_filename, "wb")
            f.write(data)
            f.close()


class Tile:

    def __init__(self, x: int, y: int, z: int, cacher: TileCacher) -> None:
        self.x = x
        self.y = y
        self.z = z
        try:
            self.tile = Image.open(cacher.get_tile_filename(self.x, self.y, self.z))
        except Exception as e:
            print(f"Error processing file {cacher.get_tile_filename(self.x, self.y, self.z)} [{e}]")
            self.tile = Image.open("error.png")

    def lat_lon_to_image_xy(self, lat_deg: float, lon_deg: float) -> (int, int):
        """ Internal. Converts lat, lon into dst_img coordinates in pixels """
        lat_rad = math.radians(lat_deg)
        n = 2.0 ** self.z
        xtile_frac = (lon_deg + 180) / 360 * n
        ytile_frac = (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2 * n
        img_x = int((xtile_frac-self.x)*osm_tile_res)
        img_y = int((ytile_frac-self.y)*osm_tile_res)
        return (img_x, img_y)

    def gpx_to_list(self, gpx) -> list[float, float]:
        points = []
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    x, y = self.lat_lon_to_image_xy(point.latitude, point.longitude)
                    if x < 0 or x > 256 or y < 0 or y > 256:
                        continue
                    points.append((x, y))
        return points

    def get_tile(self) -> Image:
        return self.tile


class TileFog(Tile):

    def __init__(self, x: int, y: int, z: int, cacher: TileCacher) -> None:
        super().__init__(x, y, z, cacher)
        self.fog = Image.open("fog.png").convert(mode="RGB")
        self.mask = Image.new("L", self.tile.size, color=20)

    def clear_fog(self, track: list[(float, float)]) -> None:
        draw = ImageDraw.Draw(self.mask)
        draw.line(track, 55, 25, joint="curve")
        draw.line(track, 105, 20, joint="curve")
        draw.line(track, 155, 15, joint="curve")
        draw.line(track, 205, 10, joint="curve")
        draw.line(track, 255, 5, joint="curve")

    def clear_fog_gpx(self, gpx) -> None:
        self.clear_fog(self.gpx_to_list(gpx))

    def get_tile(self) -> Image:
        tile = self.fog.copy()
        tile.paste(self.tile, box=None, mask=self.mask)
        return tile
