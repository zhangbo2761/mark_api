from flask import Flask, request, jsonify
from PIL import Image, ImageDraw
import io
import base64
import requests

app = Flask(__name__)

@app.route('/mark', methods=['POST'])
def mark():
    data = request.get_json()
    image_url = data.get('image_url')
    marks = data.get('marks', [])

    if not image_url:
        return jsonify({'error': 'Missing image_url'}), 400

    try:
        resp = requests.get(image_url, timeout=10)
        img = Image.open(io.BytesIO(resp.content))
    except Exception as e:
        return jsonify({'error': f'Download failed: {str(e)}'}), 400

    draw = ImageDraw.Draw(img)
    w, h = img.size

    for mark in marks:
        box = mark.get('box_2d', [])
        if len(box) != 4:
            continue
        ymin, xmin, ymax, xmax = box
        x1 = int(xmin * w) - 5
        y1 = int(ymin * h) - 5
        x2 = int(xmax * w) + 5
        y2 = int(ymax * h) + 5
        draw.ellipse([x1, y1, x2, y2], outline='red', width=3)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    img_base64 = base64.b64encode(buf.getvalue()).decode()

    return jsonify({'marked_image_base64': img_base64})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)