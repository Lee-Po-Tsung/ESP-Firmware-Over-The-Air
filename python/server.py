from flask import Flask, render_template_string, send_file, redirect, request, abort, make_response
from pathlib import Path
import tomllib
import json
from os import chdir, remove, rmdir
import datetime
import hashlib

def calculate_md5(filename):
    md5 = hashlib.md5()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5.update(chunk)
    return md5.hexdigest()

CURPATH = Path(__file__).parent
chdir(CURPATH)

app = Flask(__name__)
with open("configs.toml", "rb") as file:
    configs = tomllib.load(file)

FIRMWARE_PATH = CURPATH / configs["path"]["firmware"]
VERSION_PATH = CURPATH / configs["path"]["version_list"]
FIRMWARE_PATH.mkdir(exist_ok=True)
if not VERSION_PATH.exists():
    VERSION_PATH.write_text("{}", encoding="utf-8")

with open(VERSION_PATH, "rb") as file:
    versionList = json.load(file)

@app.route("/")
def root():
    return redirect("/firmware")

@app.route("/firmware")
def firmware_list():
    return render_template_string("""<form method='post' action='/firmware/upload' enctype="multipart/form-data"><label for='version'>版本</label><input type='text' name='version'/><br>
                                  <label for='firmware'>韌體檔案<label/><input type='file' name='firmware'/><br>
                                  <input type='submit'></form><br>
                                  <table><thead><tr><th>檔名</th><th>版本</th></tr></thead>
                                  <tbody>{% for k, v in versionList.items() %}<tr><td>{{v}}</td><td>{{k}}</td></tr>{% endfor %}</tbody>
                                  </table>""", versionList=versionList)

@app.route("/firmware/<version>")
def firmware(version: str):
    if version not in versionList:
        return abort(404)
    return send_file(FIRMWARE_PATH / versionList[version])

@app.route("/firmware/latest", methods=["GET", "HEAD"])
def firmware_latest():
    if versionList == {}:
        return abort(404)
    latest_version = list(versionList.keys())[-1]
    filepath = FIRMWARE_PATH / versionList[latest_version]

    md5_value = calculate_md5(filepath)
    file_size = filepath.stat().st_size

    res = make_response(send_file(
        FIRMWARE_PATH / versionList[latest_version],
        mimetype="application/octet-stream",
        as_attachment=True
    ))
    res.headers["X-Version"] = latest_version
    res.headers["X-MD5"] = md5_value

    return res

@app.route("/firmware/upload", methods=["POST"])
def upload():
    # print(request.form)
    # print(request.files)
    version = request.form.get("version")
    firmware = request.files.get("firmware")
    if not version or not firmware:
        return {"status": 0, "message": "Missing version or firmware file"}
    if version in versionList:
        return {"status": 0, "message": "Version already exists"}
    now = datetime.datetime.now()
    datetime_str = now.strftime('%y%m%d_%H%M%S')
    firmware.save(FIRMWARE_PATH / (datetime_str + "_" + firmware.filename))
    versionList[version] = datetime_str + "_" + firmware.filename
    with open(VERSION_PATH, "w", encoding="utf-8") as file:
        json.dump(versionList, file)
    return {"status": 1}

@app.route("/delete/<version>")
def deleteFW(version: str):
    if version not in versionList:
        return abort(404)
    remove(FIRMWARE_PATH / versionList[version])
    del versionList[version]
    with open(VERSION_PATH, "w", encoding="utf-8") as file:
        json.dump(versionList, file)
    return {"status": 1}

@app.route("/clean")
def clean():
    for version, filename in versionList.items():
        if (FIRMWARE_PATH / filename).exists():
            remove(FIRMWARE_PATH / filename)
    versionList.clear()
    remove(VERSION_PATH)
    rmdir(FIRMWARE_PATH)
    return {"status": 1}


if __name__ == '__main__':
    # from socket import gethostbyname, gethostname
    # if configs["setting"]["host"] == "0.0.0.0":
    #     print(f"http://{gethostbyname(gethostname())}:{configs['setting']['ip']}/")
    app.run(host=configs["setting"]["host"], port=configs["setting"]["ip"], debug=True)