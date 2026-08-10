from flask import Flask, request, jsonify, send_from_directory
from PIL import Image, ImageDraw
import io
import os
import json
import uuid
import requests
import traceback

app = Flask(__name__)

# Render 临时目录
IMAGE_DIR = "/tmp/marked_images"
os.makedirs(IMAGE_DIR, exist_ok=True)


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ok",
        "message": "Mark API is running",
        "endpoint": "/mark"
    })


# ---------------------------------------------------------
# 提供批改后的图片
# ---------------------------------------------------------
@app.route("/images/<filename>", methods=["GET"])
def get_image(filename):
    return send_from_directory(
        IMAGE_DIR,
        filename
    )


# ---------------------------------------------------------
# 图片批改
# ---------------------------------------------------------
@app.route("/mark", methods=["POST"])
def mark_image():

    try:

        # -------------------------------------------------
        # 1. 获取 JSON
        # -------------------------------------------------
        data = request.get_json(silent=True)

        if not data:
            return jsonify({
                "success": False,
                "error": "Invalid JSON"
            }), 400

        # -------------------------------------------------
        # 2. 图片 URL
        # -------------------------------------------------
        image_url = data.get("image_url")

        if not image_url or not isinstance(image_url, str):
            return jsonify({
                "success": False,
                "error": "未接收到有效的图片链接"
            }), 400

        # -------------------------------------------------
        # 3. marks
        # -------------------------------------------------
        marks = data.get("marks", [])

        if isinstance(marks, str):

            try:
                marks = json.loads(marks)
            except Exception:
                marks = []

        if not isinstance(marks, list):
            marks = []

        # -------------------------------------------------
        # 4. 下载图片
        # -------------------------------------------------
        headers = {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "Chrome/130.0 Safari/537.36"
            )
        }

        resp = requests.get(
            image_url,
            headers=headers,
            timeout=30,
            allow_redirects=True
        )

        if resp.status_code != 200:
            return jsonify({
                "success": False,
                "error": "图片下载失败",
                "status": resp.status_code
            }), 400

        # -------------------------------------------------
        # 5. 打开图片
        # -------------------------------------------------
        img = Image.open(
            io.BytesIO(resp.content)
        ).convert("RGB")

        draw = ImageDraw.Draw(img)

        w, h = img.size

        # -------------------------------------------------
        # 6. 画批改标记
        # -------------------------------------------------
        for mark in marks:

            if not isinstance(mark, dict):
                continue

            box = mark.get("box_2d", [])

            if not isinstance(box, list) or len(box) != 4:
                continue

            try:
                ymin, xmin, ymax, xmax = [
                    float(x) for x in box
                ]
            except Exception:
                continue

            # 判断坐标范围
            max_value = max(
                abs(ymin),
                abs(xmin),
                abs(ymax),
                abs(xmax)
            )

            if max_value <= 1:

                x1 = int(xmin * w)
                y1 = int(ymin * h)
                x2 = int(xmax * w)
                y2 = int(ymax * h)

            elif max_value <= 100:

                x1 = int(xmin / 100 * w)
                y1 = int(ymin / 100 * h)
                x2 = int(xmax / 100 * w)
                y2 = int(ymax / 100 * h)

            else:

                x1 = int(xmin / 1000 * w)
                y1 = int(ymin / 1000 * h)
                x2 = int(xmax / 1000 * w)
                y2 = int(ymax / 1000 * h)

            # 边界保护
            x1 = max(0, min(w - 1, x1))
            y1 = max(0, min(h - 1, y1))
            x2 = max(0, min(w - 1, x2))
            y2 = max(0, min(h - 1, y2))

            if x2 < x1:
                x1, x2 = x2, x1

            if y2 < y1:
                y1, y2 = y2, y1

            mark_type = mark.get(
                "type",
                "circle"
            )

            # -------------------------------------------------
            # 圆圈
            # -------------------------------------------------
            if mark_type == "circle":

                draw.ellipse(
                    [
                        max(0, x1 - 6),
                        max(0, y1 - 6),
                        min(w - 1, x2 + 6),
                        min(h - 1, y2 + 6)
                    ],
                    outline="red",
                    width=4
                )

            # -------------------------------------------------
            # 红叉
            # -------------------------------------------------
            elif mark_type == "cross":

                draw.line(
                    [(x1, y1), (x2, y2)],
                    fill="red",
                    width=4
                )

                draw.line(
                    [(x1, y2), (x2, y1)],
                    fill="red",
                    width=4
                )

            # -------------------------------------------------
            # 红框
            # -------------------------------------------------
            else:

                draw.rectangle(
                    [x1, y1, x2, y2],
                    outline="red",
                    width=4
                )

        # -------------------------------------------------
        # 7. 保存图片
        # -------------------------------------------------
        filename = (
            str(uuid.uuid4())
            + ".png"
        )

        filepath = os.path.join(
            IMAGE_DIR,
            filename
        )

        img.save(
            filepath,
            format="PNG"
        )

        # -------------------------------------------------
        # 8. 生成公开 URL
        # -------------------------------------------------
        host = request.host_url.rstrip("/")

        image_url_result = (
            host
            + "/images/"
            + filename
        )

        # -------------------------------------------------
        # 9. 返回
        # -------------------------------------------------
        return jsonify({
            "success": True,
            "marked_image_url": image_url_result,
            "marks_count": len(marks),
            "image_width": w,
            "image_height": h
        })

    except Exception as e:

        print(traceback.format_exc())

        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
    )