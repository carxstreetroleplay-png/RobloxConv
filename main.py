from flask import Flask, jsonify, request
import requests
import re
import os

app = Flask(__name__)

ROBLOSECURITY = os.environ.get("ROBLOSECURITY", "")

# Maps share-link "type" param to the key Roblox nests the result under
SHARE_TYPE_KEY_MAP = {
    "AvatarItemDetails": "avatarItemDetailsData",
    "ExperienceDetails": "experienceDetailsInviteData",
}


def extract_from_url(url):
    """Try to extract ID directly from URL patterns (no auth needed)"""
    patterns = [
        (r'/catalog/(\d+)', 'catalog'),
        (r'/bundles/(\d+)', 'bundle'),
        (r'/game-pass/(\d+)', 'gamepass'),
        (r'/game-passes/(\d+)', 'gamepass'),
        (r'/item/(\d+)', 'catalog'),
    ]
    for pattern, item_type in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1), item_type
    return None, None


def resolve_share_code(code, share_type="AvatarItemDetails"):
    """Use Roblox's confirmed sharelinks resolve API, handling CSRF retry."""
    session = requests.Session()
    session.cookies.set(".ROBLOSECURITY", ROBLOSECURITY, domain=".roblox.com")

    url = "https://apis.roblox.com/sharelinks/v1/resolve-link"
    payload = {"linkId": code, "linkType": share_type}

    r = session.post(url, json=payload, timeout=10)

    if r.status_code == 403 and "x-csrf-token" in r.headers:
        session.headers.update({"x-csrf-token": r.headers["x-csrf-token"]})
        r = session.post(url, json=payload, timeout=10)

    if r.status_code != 200:
        return None, f"http_{r.status_code}: {r.text[:200]}"

    data = r.json()
    data_key = SHARE_TYPE_KEY_MAP.get(share_type)
    item_data = data.get(data_key) if data_key else None

    if not item_data:
        return None, f"unsupported_share_type_or_empty: {data}"

    if item_data.get("status") != "Valid":
        return None, f"status_{item_data.get('status')}: {data}"

    return item_data.get("itemId"), item_data.get("itemType")


def resolve_via_redirect(url):
    """Fallback: follow redirect and scrape ID from final URL or page HTML."""
    try:
        session = requests.Session()
        session.cookies.set(".ROBLOSECURITY", ROBLOSECURITY, domain=".roblox.com")
        r = session.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            allow_redirects=True,
            timeout=10
        )

        final_url = r.url

        item_id, item_type = extract_from_url(final_url)
        if item_id:
            return item_id, item_type

        patterns_html = [
            r'"assetId"\s*:\s*(\d+)',
            r'"AssetId"\s*:\s*(\d+)',
            r'"itemId"\s*:\s*(\d+)',
            r'"bundleId"\s*:\s*(\d+)',
            r'/catalog/(\d+)',
            r'/bundles/(\d+)',
        ]
        for pattern in patterns_html:
            match = re.search(pattern, r.text)
            if match:
                return match.group(1), 'scraped'

        return None, f"redirect_no_id: final={final_url}"

    except Exception as e:
        return None, f"redirect_exception: {str(e)}"


@app.route('/')
def index():
    return jsonify({
        'status': 'online',
        'usage': '/resolve?url=YOUR_ROBLOX_URL',
        'examples': [
            '/resolve?url=https://www.roblox.com/catalog/108875151/item',
            '/resolve?url=https://www.roblox.com/bundles/591/Mr-Toilet',
            '/resolve?url=https://www.roblox.com/game-pass/1571040498/name',
            '/resolve?url=https://www.roblox.com/share?code=xxx&type=AvatarItemDetails',
        ]
    })


@app.route('/resolve')
def resolve():
    url = request.args.get('url', '').strip()

    if not url:
        return jsonify({'error': 'missing_url'}), 400

    if url.isdigit():
        return jsonify({'id': url, 'source': 'direct'})

    item_id, item_type = extract_from_url(url)
    if item_id:
        return jsonify({'id': item_id, 'type': item_type, 'source': 'url_pattern'})

    code_match = re.search(r'code=([^&]+)', url)
    if code_match:
        code = code_match.group(1)
        type_match = re.search(r'type=([^&]+)', url)
        share_type = type_match.group(1) if type_match else "AvatarItemDetails"

        item_id, result = resolve_share_code(code, share_type)
        if item_id:
            return jsonify({'id': item_id, 'type': result, 'source': 'share_api'})

        print(f"[share_api failed] {result}")

        item_id, item_type = resolve_via_redirect(url)
        if item_id:
            return jsonify({'id': item_id, 'type': item_type, 'source': 'redirect_scrape'})

        return jsonify({
            'error': 'share_code_unresolvable',
            'detail': result,
            'tip': 'Open the share link in browser, copy the redirected URL, paste that instead'
        }), 400

    item_id, item_type = resolve_via_redirect(url)
    if item_id:
        return jsonify({'id': item_id, 'type': item_type, 'source': 'redirect_scrape'})

    return jsonify({'error': 'no_id_found', 'url': url}), 400


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
