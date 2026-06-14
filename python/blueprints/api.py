from flask import Blueprint, request, current_app, abort, make_response, send_file
from utils import get_version_list, compare_version

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/check", methods=["POST"])
def check_update():
    req_data = request.get_json()
    if not req_data or "ID" not in req_data or "version" not in req_data:
        return abort(400)

    ID = req_data["ID"]
    version = req_data["version"]

    versionList = get_version_list()

    if ID not in versionList:
        print(ID)
        return abort(403)

    device_info = versionList[ID]
    latest_version = device_info["version"]

    if not compare_version(latest_version, version):
        return {"update_available": False}

    return {
        "update_available": True,
        "ID": ID,
        "version": latest_version,
        "signature": device_info["signature"],
        "download_url": f"/api/download/{ID}",
    }


@api_bp.route("/download/<ID>", methods=["GET"])
def download_firmware(ID: str):
    versionList = get_version_list()
    if ID not in versionList:
        return abort(404)

    filename = versionList[ID]["filename"]
    filepath = current_app.config["FIRMWARE_PATH"] / filename

    if not filepath.exists():
        return abort(404)

    res = make_response(
        send_file(filepath, mimetype="application/octet-stream", as_attachment=True)
    )

    return res
