from flask import Flask, request, jsonify
from PIL import Image, ImageDraw
import io
import base64
import requests

app = Flask(__name__)

@app.route('/')
def home():
    return "API is running!"

@app.route('/mark', methods=['POST'])
def mark_image():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
            
        image_url = data.get('image_url')
        marks = data.get('marks', [])

        if not image_url:
            return jsonify({'error': 'No image_url'}), 400

        # 下载图片
        resp = requests.get(image_url, timeout=15)
        if resp.status_code != 200:
            return jsonify({'error': f'Failed to download image, status: {resp.status_code}'}), 400

        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        draw = ImageDraw.Draw(img)
        w, h = img.size

        for mark in marks:
            box = mark.get('box_2d', [])
            if len(box) != 4:
                continue
            
            ymin, xmin, ymax, xmax = box
            
            # 智能自适应坐标归一化（防止越界报错）
            if xmax > 1.0 or ymax > 1.0:
                if xmax > 100.0 or ymax > 100.0: # 兼容 0-1000
                    x1, y1 = int((xmin / 1000.0) * w), int((ymin / 1000.0) * h)
                    x2, y2 = int((xmax / 1000.0) * w), int((ymax / 1000.0) * h)
                else: # 兼容 0-100
                    x1, y1 = int((xmin / 100.0) * w), int((ymin / 100.0) * h)
                    x2, y2 = int((xmax / 100.0) * w), int((ymax / 100.0) * h)
            else: # 兼容 0-1 小数
                x1, y1 = int(xmin * w), int(ymin * h)
                x2, y2 = int(xmax * w), int(ymax * h)

            # 确保坐标不超出图片边界
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            typ = mark.get('type', 'cross')

            if typ == 'circle':
                draw.ellipse([x1-5, y1-5, x2+5, y2+5], outline='red', width=3)
            elif typ == 'check':
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                draw.line([(x1, cy), (cx, y2), (x2, y1)], fill='green', width=4)
            else: # 默认画红叉/红框
                draw.rectangle([x1, y1, x2, y2], outline='red', width=4)
                
            # 如果有评语，可以在框上方写字
            comment = mark.get('comment') or mark.get('text')
            if comment:
                try:
                    draw.text((x1, max(0, y1 - 15)), str(comment), fill='red')
                except:
                    pass

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        img_base64 = base64.b64encode(buf.getvalue()).decode()
        return jsonify({'marked_image_base64': img_base64})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)