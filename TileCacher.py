from typing import Final
import yaml
import os
import requests

# Constants
osm_tile_res: Final = 256
server_file: Final = "server.yaml"


class TileCacher:
    """ Class for caching tiles """

    def __init__(self, _map: str, folder: str = "tmp") -> None:
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
