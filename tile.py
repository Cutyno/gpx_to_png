import math
from PIL import Image, ImageDraw
from TileCacher import TileCacher, osm_tile_res


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
