import io
import zipfile
import csv
import sys
import os

sys.path.append(os.path.join(os.getcwd(), 'grand_river_current/pkg_ingest'))
import requests

STATIC_URL = "https://webapps.regionofwaterloo.ca/api/grt-routes/api/staticfeeds/0"

# Minimal Adapter for SSL issues
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from urllib3.util.ssl_ import create_urllib3_context

class LegacyAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        ctx = create_urllib3_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        self.poolmanager = PoolManager(
            num_pools=connections, maxsize=maxsize, block=block, ssl_context=ctx
        )

def check_block_id():
    print(f"Checking for block_id in {STATIC_URL}...")
    s = requests.Session()
    s.mount('https://', LegacyAdapter())
    r = s.get(STATIC_URL)
    
    z = zipfile.ZipFile(io.BytesIO(r.content))
    
    with z.open('trips.txt') as f:
        reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
        row = next(reader)
        if 'block_id' in row:
            print("SUCCESS: block_id found in trips.txt")
            print(f"Sample: {row}")
        else:
            print("FAILURE: block_id NOT found.")

if __name__ == '__main__':
    check_block_id()
