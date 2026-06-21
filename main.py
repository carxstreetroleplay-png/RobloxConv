from flask import Flask, jsonify, request
import requests
import os
import re
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)

ROBLOSECURITY = os.environ.get("ROBLOSECURITY", "")


def resolve_via_api(share_code, item_type, roblosecurity):
    session = requests.Session()
    session.cookies.set(".ROBLOSECURITY", roblosecurity, domain=".roblox.com")

    url = "https://apis.roblox.com/sharelinks/v1/resolve-link"
    payload = {"linkId": share_code, "linkType": item_type}

    r = session.post(url, json=payload)

    if r.status_code == 403 and "x-csrf-token" in r.headers:
        csrf_token = r.headers["x-csrf-token"]
        session.headers.update({"x-csrf-token": csrf_token})
        r = session.post(url, json=payload)

    return r.json()


@app.route('/resolve')
def resolve():
    share_url = request.args.get('url')

    if not share_url:
        return jsonify({'error': 'missing_url'}), 400

    if not ROBLOSECURITY:
        return jsonify({'error': 'server_missing_cookie'}), 500

    parsed = urlparse(share_url)
    qs = parse_qs(parsed.query)

    code = qs.get('code', [None])[0]
    item_type = qs.get('type', ['AvatarItemDetails'])[0]

    if not code:
        return jsonify({'error': 'url_missing_code_param', 'url': share_url}), 400

    result = resolve_via_api(code, item_type, ROBLOSECURITY)
    return jsonify(result)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
