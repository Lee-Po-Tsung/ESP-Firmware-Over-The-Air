from flask import Flask, redirect
from pathlib import Path
import tomllib
from os import chdir

from blueprints.firmware import firmware_bp
from blueprints.api import api_bp
from utils import generate_self_signed_cert

CURPATH = Path(__file__).parent
chdir(CURPATH)

app = Flask(__name__)

with open("configs.toml", "rb") as file:
    configs = tomllib.load(file)

app.config["FIRMWARE_PATH"] = CURPATH / configs["path"]["firmware"]
app.config["VERSION_PATH"] = CURPATH / configs["path"]["version_list"]
app.config["PRIVATE_KEY_PATH"] = CURPATH / configs["path"]["private_key"]
app.config["PUBLIC_KEY_PATH"] = CURPATH / configs["path"]["public_key"]
app.config["ADMIN_KEY"] = configs["setting"].get("admin_key", "")
app.config["CERT_PATH"] = CURPATH / configs["path"]["cert"]
app.config["KEY_PATH"] = CURPATH / configs["path"]["key"]

# Generate self-signed certificate if they do not exist
if not app.config["CERT_PATH"].exists() or not app.config["KEY_PATH"].exists():
    print("Generating self-signed SSL certificate...")
    generate_self_signed_cert(app.config["CERT_PATH"], app.config["KEY_PATH"])

app.config["FIRMWARE_PATH"].mkdir(exist_ok=True)
if not app.config["VERSION_PATH"].exists():
    app.config["VERSION_PATH"].write_text("{}", encoding="utf-8")

app.register_blueprint(firmware_bp)
app.register_blueprint(api_bp)


@app.route("/")
def root():
    return redirect("/firmware")


if __name__ == "__main__":
    # from socket import gethostbyname, gethostname
    # if configs["setting"]["host"] == "0.0.0.0":
    #     print(f"http://{gethostbyname(gethostname())}:{configs['setting']['ip']}/")
    app.run(
        host=configs["setting"]["host"],
        port=configs["setting"]["ip"],
        ssl_context=(str(app.config["CERT_PATH"]), str(app.config["KEY_PATH"])),
        debug=True,
    )
