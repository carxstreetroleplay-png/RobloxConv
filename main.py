from flask import Flask, jsonify, request
import requests
import os

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
    code = request.args.get('code')
    item_type = request.args.get('type', 'AvatarItemDetails')

    if not code:
        return jsonify({'error': 'missing_code'}), 400

    if not ROBLOSECURITY:
        return jsonify({'error': 'server_missing_cookie'}), 500

    result = resolve_via_api(code, item_type, ROBLOSECURITY)
    return jsonify(result)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
