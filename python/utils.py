import hashlib
import json
import base64
import datetime
from flask import current_app
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key, Encoding, PrivateFormat, NoEncryption
from cryptography import x509
from cryptography.x509.oid import NameOID



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


def generate_self_signed_cert(cert_path, key_path):
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "TW"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Taiwan"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Taipei"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Antigravity"),
        x509.NameAttribute(NameOID.COMMON_NAME, "leepotsung.pythonanywhere.com"),
    ])
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.now(datetime.timezone.utc)
    ).not_valid_after(
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650)
    ).add_extension(
        x509.SubjectAlternativeName([x509.DNSName("leepotsung.pythonanywhere.com")]),
        critical=False,
    ).sign(private_key, hashes.SHA256())

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(Encoding.PEM))
    with open(key_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=NoEncryption()
        ))
