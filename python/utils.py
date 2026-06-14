import hashlib
import json
import base64
from flask import current_app
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key


def calculate_sha256(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def sign_manifest(model, version, file_path):
    file_hash = calculate_sha256(file_path)

    manifest_str = f"{model}|{version}|{file_hash}"
    manifest_bytes = manifest_str.encode("utf-8")

    with open(current_app.config["PRIVATE_KEY_PATH"], "rb") as key_file:
        private_key = load_pem_private_key(key_file.read(), password=None)

    signature = private_key.sign(
        manifest_bytes,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def get_version_list():
    with open(current_app.config["VERSION_PATH"], "rb") as file:
        return json.load(file)


def save_version_list(data):
    with open(current_app.config["VERSION_PATH"], "w", encoding="utf-8") as file:
        json.dump(data, file)


def compare_version(latest_v, current_v):
    return list(map(int, latest_v.split(".", 2))) > list(map(int, current_v.split(".", 2)))
