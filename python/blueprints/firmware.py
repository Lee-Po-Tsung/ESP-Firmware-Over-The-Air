from flask import Blueprint, render_template_string, request, current_app
import datetime
from utils import get_version_list, save_version_list

firmware_bp = Blueprint("firmware", __name__, url_prefix="/firmware")

from flask import Blueprint, render_template_string, request, current_app
import datetime
from utils import get_version_list, save_version_list, sign_manifest

firmware_bp = Blueprint("firmware", __name__, url_prefix="/firmware")


@firmware_bp.route("")
def firmware_list():
    versionList = get_version_list()
    return render_template_string(
        """<form method='post' action='/firmware/upload' enctype="multipart/form-data">
                                  <label for='model'>型號</label><input type='text' name='model'/><br>
                                  <label for='version'>版本</label><input type='text' name='version'/><br>
                                  <label for='firmware'>韌體檔案</label><input type='file' name='firmware'/><br>
                                  <input type='submit'></form><br>
                                  <table border="1"><thead><tr><th>型號</th><th>最新版本</th><th>檔名</th></tr></thead>
                                  <tbody>{% for model, data in versionList.items() %}<tr><td>{{model}}</td><td>{{data.version}}</td><td>{{data.filename}}</td></tr>{% endfor %}</tbody>
                                  </table>""",
        versionList=versionList,
    )


@firmware_bp.route("/upload", methods=["POST"])
def upload():
    model = request.form.get("model")
    version = request.form.get("version")
    firmware_file = request.files.get("firmware")

    if not model or not version or not firmware_file:
        return {"status": 0, "message": "Missing model, version or firmware file"}

    now = datetime.datetime.now()
    datetime_str = now.strftime("%y%m%d_%H%M%S")
    filename = datetime_str + "_" + firmware_file.filename
    filepath = current_app.config["FIRMWARE_PATH"] / filename

    firmware_file.save(filepath)

    signature = sign_manifest(model, version, filepath)

    versionList = get_version_list()
    versionList[model] = {"version": version, "filename": filename, "signature": signature}
    save_version_list(versionList)

    return {"status": 1}
