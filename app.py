from flask import Flask, request, jsonify
from PIL import Image, ImageDraw
import io
import base64
import requests
import traceback
import json

app = Flask(__name__)


@app.route("/")
def home():
    return "API is running!"


@app.route("/mark", methods=["POST"])
def mark_image():
    try:
        print("\n===============================", flush=True)
        print("收到新的请求", flush=True)

        # 打印Headers
        print("Headers:", dict(request.headers), flush=True)

        # 打印原始Body
        print("Raw Body:", request.get_data(as_text=True), flush=True)

        # 获取JSON
        data = request.get_json(silent=True)

        print("JSON:", data, flush=True)

        if data is None:
            return jsonify({
                "error": "Request is not valid JSON"
            }), 400

        image_url = data.get("image_url")
        marks = data.get("marks", [])

        print("image_url =", image_url, flush=True)
        print("marks type =", type(marks), flush=True)
        print("marks =", marks, flush=True)

        if not image_url:
            return jsonify({
                "error": "image_url为空"
            }), 400

        # 如果marks是字符串，自动转JSON
        if isinstance(marks, str):
            try:
                marks = json.loads(marks)
                print("marks字符串已解析成功", flush=True)
            except Exception:
                print("marks不是合法JSON字符串", flush=True)
                marks = []

        # 下载图片
        print("开始下载图片...", flush=True)

        resp = requests.get(image_url, timeout=30)

        print("下载状态码:", resp.status_code, flush=True)
        print("Content-Type:", resp.headers.get("Content-Type"), flush=True)

        if resp.status_code != 200:
            return jsonify({
                "error": f"下载图片失败，HTTP {resp.status_code}",
                "response": resp.text[:500]
            }), 400

        if "image" not in resp.headers.get("Content-Type", ""):
            return jsonify({
                "error": "下载到的不是图片",
                "content_type": resp.headers.get("Content-Type"),
                "body": resp.text[:500]
            }), 400

        img = Image.open(io.BytesIO(resp.content)).convert("RGB")

        draw = ImageDraw.Draw(img)

        width, height = img.size

        print("图片大小:", width, height, flush=True)

        for i, mark in enumerate(marks):

            print(f"\n处理第 {i+1} 个mark:", mark, flush=True)

            if not isinstance(mark, dict):
                print("mark不是dict，跳过", flush=True)
                continue

            box = mark.get("box_2d") or mark.get("box") or []

            if len(box) != 4:
                print("box长度错误", box, flush=True)
                continue

            try:
                ymin = float(box[0])
                xmin = float(box[1])
                ymax = float(box[2])
                xmax = float(box[3])
            except Exception:
                print("box无法转换数字", box, flush=True)
                continue

            # 坐标自动识别
            if xmax <= 1 and ymax <= 1:
                x1 = int(xmin * width)
                y1 = int(ymin * height)
                x2 = int(xmax * width)
                y2 = int(ymax * height)

            elif xmax <= 100 and ymax <= 100:
                x1 = int(xmin / 100 * width)
                y1 = int(ymin / 100 * height)
                x2 = int(xmax / 100 * width)
                y2 = int(ymax / 100 * height)

            else:
                x1 = int(xmin / 1000 * width)
                y1 = int(ymin / 1000 * height)
                x2 = int(xmax / 1000 * width)
                y2 = int(ymax / 1000 * height)

            x1 = max(0, min(width - 1, x1))
            y1 = max(0, min(height - 1, y1))
            x2 = max(0, min(width - 1, x2))
            y2 = max(0, min(height - 1, y2))

            typ = mark.get("type", "circle")

            if typ == "circle":
                draw.ellipse(
                    [x1, y1, x2, y2],
                    outline="red",
                    width=4
                )

            elif typ == "check":

                cx = (x1 + x2) // 2

                draw.line(
                    [(x1, y2), (cx, y1), (x2, y2)],
                    fill="green",
                    width=5
                )

            else:

                draw.rectangle(
                    [x1, y1, x2, y2],
                    outline="red",
                    width=4
                )

            comment = mark.get("comment") or mark.get("text")

            if comment:
                try:
                    draw.text(
                        (x1, max(0, y1 - 18)),
                        str(comment),
                        fill="red"
                    )
                except Exception:
                    pass

        buffer = io.BytesIO()

        img.save(buffer, format="PNG")

        img_base64 = base64.b64encode(buffer.getvalue()).decode()

        print("图片处理完成", flush=True)

        return jsonify({
            "marked_image_base64": img_base64
        })

    except Exception as e:

        print("\n########## 发生异常 ##########", flush=True)

        traceback.print_exc()

        print(str(e), flush=True)

        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)