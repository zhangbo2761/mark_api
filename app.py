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

    # 防止Dify没传图或者传了{{...}}原文本导致崩溃
    if not image_url or "{{" in image_url:
        return jsonify({"error": "未接收到有效的图片链接，请确保Dify预览时已上传图片"}), 400

    # 使用 timeout=60 预防免费版冷启动超时
    resp = requests.get(image_url, timeout=60)
    img = Image.open(io.BytesIO(resp.content))
    draw = ImageDraw.Draw(img)
    w, h = img.size

    for m in marks:
        box = m.get('box_2d', [])
        if len(box) != 4:
            continue
        ymin, xmin, ymax, xmax = box
        x1, y1 = int(xmin * w) - 5, int(ymin * h) - 5
        x2, y2 = int(xmax * w) + 5, int(ymax * h) + 5
        draw.ellipse([x1, y1, x2, y2], outline='red', width=3)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    img_base64 = base64.b64encode(buf.getvalue()).decode()
    return jsonify({'marked_image_base64': img_base64})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)