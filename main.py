from flask import Flask, jsonify, request
import requests
import re
import os

app = Flask(__name__)

ROBLOSECURITY = os.environ.get("ROBLOSECURITY", "")

def extract_from_url(url):
    """Try to extract ID directly from URL patterns"""
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
    """Try to resolve share code using Roblox API with cookie auth"""
    try:
        r = requests.get(
            "https://share.roblox.com/v1/resolve",
            params={"code": code, "type": share_type},
            cookies={".ROBLOSECURITY": ROBLOSECURITY},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Referer": "https://www.roblox.com",
                "Origin": "https://www.roblox.com",
            },
            timeout=10
        )

        print(f"[share.roblox.com] status={r.status_code} body={r.text[:300]}")

        if r.status_code == 200:
            data = r.json()
            item_id = (
                data.get('assetId') or
                data.get('AssetId') or
                data.get('id') or
                data.get('Id') or
                data.get('itemId') or
                data.get('ItemId')
            )
            if item_id:
                return str(item_id), None
            return None, f"no_id_in_response: {data}"
        
        return None, f"roblox_api_error_{r.status_code}: {r.text[:200]}"

    except Exception as e:
        return None, f"exception: {str(e)}"

def resolve_via_redirect(url):
    """Follow redirect and scrape ID from final URL or page"""
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
        print(f"[redirect] final_url={final_url}")

        # Try extract ID from final redirected URL
        item_id, item_type = extract_from_url(final_url)
        if item_id:
            return item_id, item_type

        # Try scrape from page HTML
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

# -----------------------------------------------------------------------

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

    # Plain number ID passed directly
    if url.isdigit():
        return jsonify({'id': url, 'source': 'direct'})

    # Step 1 — Try extract ID from URL directly (fastest, no auth needed)
    item_id, item_type = extract_from_url(url)
    if item_id:
        return jsonify({'id': item_id, 'type': item_type, 'source': 'url_pattern'})

    # Step 2 — Share code found in URL
    code_match = re.search(r'code=([^&]+)', url)
    if code_match:
        code = code_match.group(1)

        # Get type from URL if present
        type_match = re.search(r'type=([^&]+)', url)
        share_type = type_match.group(1) if type_match else "AvatarItemDetails"

        # Try share API first
        item_id, err = resolve_share_code(code, share_type)
        if item_id:
            return jsonify({'id': item_id, 'source': 'share_api'})

        print(f"[share_api failed] {err}")

        # Fallback: follow redirect and scrape
        item_id, item_type = resolve_via_redirect(url)
        if item_id:
            return jsonify({'id': item_id, 'type': item_type, 'source': 'redirect_scrape'})

        print(f"[redirect failed] {item_type}")

        return jsonify({
            'error': 'share_code_unresolvable',
            'detail': err,
            'tip': 'Open the share link in browser, copy the redirected URL, paste that instead'
        }), 400

    # Step 3 — Unknown URL format, try redirect anyway
    item_id, item_type = resolve_via_redirect(url)
    if item_id:
        return jsonify({'id': item_id, 'type': item_type, 'source': 'redirect_scrape'})

    return jsonify({'error': 'no_id_found', 'url': url}), 400

# -----------------------------------------------------------------------

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
