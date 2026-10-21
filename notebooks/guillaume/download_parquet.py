import os, sys
sys.path.append(".")

import conf

import pycurl
from io import BytesIO

def progress(download_t, download_d, upload_t, upload_d):
    download_done = 0
    if download_t > 0:
        download_done = download_d / download_t
    print(f"               \r{download_done}", end='')

if not os.path.exists(conf.nutriscope_root_dir):
    print(f"Le répertoire de l'application n'est pas présent: {conf.nutriscope_root_dir}")
    exit()

if not os.path.exists(conf.cache_dir):
    os.mkdir(conf.cache_dir)

if "--clear" in sys.argv:
    print(f"Netoyage du fichier parquet précédent.")

if os.path.exists(conf.off_parquet_path):
    print(f"Fichier parquet déjà présent... Relancer le script avec \"--clear\" pour le netoyer !")
    exit()

buffer = BytesIO()

curl = pycurl.Curl()
curl.setopt(curl.URL, conf.off_parquet_url)
curl.setopt(curl.WRITEDATA, buffer)
curl.setopt(curl.NOPROGRESS, False)
curl.setopt(curl.XFERINFOFUNCTION, progress)
curl.setopt(curl.FOLLOWLOCATION, 1)
curl.perform()
curl.close()

with open(conf.off_parquet_path, "a") as cache_file:
  cache_file.write(buffer.getvalue().decode())
