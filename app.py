from flask import Flask, request, jsonify
from PIL import Image, ImageDraw
import io, base64, requests

app = Flask(__name__)

@app.route('/mark', methods=['POST'])
def mark():
    data = request.get_json()
    image_url = data.get('image_url')
    marks = data.get('marks', [])
    if not image_url:
        return jsonify({'error': 'no image_url'}), 400
    # 如果 Dify 传来的是 {{...}} 这种格式，或者链接是空的，直接报错返回，不再让程序崩溃
if not image_url or "{{" in image_url:
    return {"error": "未接收到有效的图片链接，请确保Dify预览时已上传图片"}, 400

resp = requests.get(image_url, timeout=10)
    img = Image.open(io.BytesIO(resp.content))
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for m in marks:
        box = m.get('box_2d', [])
        if len(box) != 4: continue
        ymin, xmin, ymax, xmax = box
        x1, y1 = int(xmin*w)-5, int(ymin*h)-5
        x2, y2 = int(xmax*w)+5, int(ymax*h)+5
        draw.ellipse([x1, y1, x2, y2], outline='red', width=3)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    img_base64 = base64.b64encode(buf.getvalue()).decode()
    return jsonify({'marked_image_base64': img_base64})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)