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


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "missing query"}), 400
    if len(query) > 50:
        return jsonify({"error": "query too long"}), 400

    try:
        limit = min(int(request.args.get("limit", 30)), 30)
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400

    try:
        url = (
            "https://catalog.roblox.com/v1/search/items/details"
            f"?Keyword={requests.utils.quote(query)}&Limit={limit}&SortType=3"
        )
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        print("search error:", e)
        return jsonify({"error": "roblox catalog error"}), 502
    except Exception as e:
        print("search error:", e)
        return jsonify({"error": "search failed"}), 500

    items = [
        {
            "id": item["id"],
            "name": item["name"],
            "price": item.get("price"),          # null in JSON becomes None
            "itemType": item["itemType"],
            "creator": item["creatorName"],
        }
        for item in data.get("data", [])
    ]

    return jsonify({"items": items})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
