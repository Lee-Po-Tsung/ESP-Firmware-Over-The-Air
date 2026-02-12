from flask import Flask, render_template_string, send_file, redirect
from pathlib import Path
import tomllib
import json
from os import chdir

CURPATH = Path(__file__).parent
chdir(CURPATH)

app = Flask(__name__)
with open("configs.toml", "rb") as file:
    configs = tomllib.load(file)

FIRMWARE_PATH = CURPATH / configs["path"]["firmware"]
VERSION_PATH = CURPATH / configs["path"]["version_list"]
if not VERSION_PATH.exists():
    VERSION_PATH.write_text("[]", encoding="utf-8")

with open(VERSION_PATH, "rb") as file:
    versionList = json.load(file)

@app.route("/")
def root():
    return redirect("/firmware")

@app.route("/firmware")
def firmware_list():
    return render_template_string()

@app.route("/firmware/<version>")
def firmware(version: str):
    return send_file(version)

if __name__ == '__main__':
    # from socket import gethostbyname, gethostname
    # if configs["setting"]["host"] == "0.0.0.0":
    #     print(f"http://{gethostbyname(gethostname())}:{configs['setting']['ip']}/")
    app.run(host=configs["setting"]["host"], port=configs["setting"]["ip"])