from flask import Flask, jsonify, request
import requests
import re

app = Flask(__name__)

# Paste your cookie here
ROBLOSECURITY = "YOUR_.ROBLOSECURITY_COOKIE_HERE"

@app.route('/resolve')
def resolve():
    url = request.args.get('url', '')
    
    # Extract ID directly from URL patterns (no auth needed)
    patterns = [
        r'/catalog/(\d+)',
        r'/bundles/(\d+)',
        r'/game-pass/(\d+)',
        r'/item/(\d+)',
        r'/game-passes/(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return jsonify({'id': match.group(1), 'source': 'url'})

    # Share code - try resolve with Roblox cookie auth
    code_match = re.search(r'code=([^&]+)', url)
    if code_match:
        code = code_match.group(1)
        share_type = "AvatarItemDetails"
        
        # Check type from URL
        type_match = re.search(r'type=([^&]+)', url)
        if type_match:
            share_type = type_match.group(1)

        try:
            r = requests.get(
                "https://share.roblox.com/v1/resolve",
                params={"code": code, "type": share_type},
                cookies={".ROBLOSECURITY": ROBLOSECURITY},
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/json",
                    "Referer": "https://www.roblox.com"
                },
                timeout=10
            )
            print("Share API status:", r.status_code)
            print("Share API response:", r.text[:300])

            if r.status_code == 200:
                data = r.json()
                item_id = (
                    data.get('assetId') or 
                    data.get('id') or
                    data.get('AssetId') or 
                    data.get('itemId') or
                    data.get('ItemId')
                )
                if item_id:
                    return jsonify({'id': str(item_id), 'source': 'share'})
                # Return raw so we can see what fields exist
                return jsonify({'error': 'no_id_field', 'raw': data}), 400
            else:
                return jsonify({
                    'error': f'roblox_api_{r.status_code}', 
                    'raw': r.text[:200]
                }), 400

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'no_id_found'}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
