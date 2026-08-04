from flask import Flask, request, jsonify
from PIL import Image, ImageDraw
import io
import base64
import requests

app = Flask(__name__)

@app.route('/mark', methods=['POST'])
def mark_image():
    data = request.get_json()
    image_url = data.get('image_url')
    marks = data.get('marks', [])

    if not image_url:
        return jsonify({'error': 'No image_url'}), 400

    resp = requests.get(image_url)
    img = Image.open(io.BytesIO(resp.content))
    draw = ImageDraw.Draw(img)
    w, h = img.size

    for mark in marks:
        box = mark.get('box_2d', [])
        if len(box) != 4:
            continue
        ymin, xmin, ymax, xmax = box
        x1, y1 = int(xmin * w), int(ymin * h)
        x2, y2 = int(xmax * w), int(ymax * h)
        typ = mark.get('type', 'circle')

        if typ == 'circle':
            draw.ellipse([x1-5, y1-5, x2+5, y2+5], outline='red', width=3)
        elif typ == 'check':
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            draw.line([(x1, cy), (cx, y2), (x2, y1)], fill='green', width=4)
        elif typ == 'cross':
            draw.line([(x1, y1), (x2, y2)], fill='red', width=4)
            draw.line([(x2, y1), (x1, y2)], fill='red', width=4)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    img_base64 = base64.b64encode(buf.getvalue()).decode()
    return jsonify({'marked_image_base64': img_base64})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)