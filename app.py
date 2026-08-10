from flask import Flask, request, jsonify
from PIL import Image, ImageDraw
import io
import base64
import requests
import traceback

app = Flask(__name__)

# ---------------------------------------------------------
# 首页
# ---------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ok",
        "message": "Mark API is running",
        "endpoint": "/mark"
    })


# ---------------------------------------------------------
# 图片标注接口
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
                "error": "Invalid JSON",
                "received": request.data.decode("utf-8", errors="ignore")
            }), 400

        # -------------------------------------------------
        # 2. 获取图片 URL
        # -------------------------------------------------
        image_url = data.get("image_url")

        if not image_url or not isinstance(image_url, str):
            return jsonify({
                "error": "未接收到有效的图片链接",
                "received_image_url": str(image_url)
            }), 400

        # -------------------------------------------------
        # 3. 获取 marks
        # -------------------------------------------------
        marks = data.get("marks", [])

        # 如果 Dify 传过来的是字符串，尝试解析
        if isinstance(marks, str):
            import json

            try:
                marks = json.loads(marks)
            except Exception:
                return jsonify({
                    "error": "marks 不是有效 JSON",
                    "marks_received": marks
                }), 400

        if not isinstance(marks, list):
            marks = []

        # -------------------------------------------------
        # 4. 下载图片
        # -------------------------------------------------
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
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
                "error": "图片下载失败",
                "status": resp.status_code,
                "url": image_url
            }), 400

        if not resp.content:
            return jsonify({
                "error": "下载到的图片内容为空"
            }), 400

        # -------------------------------------------------
        # 5. 打开图片
        # -------------------------------------------------
        try:
            img = Image.open(io.BytesIO(resp.content))
            img.load()
            img = img.convert("RGB")
        except Exception as e:
            return jsonify({
                "error": "无法解析图片",
                "detail": str(e),
                "content_type": resp.headers.get("Content-Type"),
                "content_length": len(resp.content)
            }), 400

        draw = ImageDraw.Draw(img)

        w, h = img.size

        # -------------------------------------------------
        # 6. 处理每一个批改框
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

            # -------------------------------------------------
            # 支持三种坐标：
            #
            # 0~1
            # 0~100
            # 0~1000
            # -------------------------------------------------

            max_value = max(
                abs(ymin),
                abs(xmin),
                abs(ymax),
                abs(xmax)
            )

            if max_value <= 1:
                # 0~1
                x1 = int(xmin * w)
                y1 = int(ymin * h)
                x2 = int(xmax * w)
                y2 = int(ymax * h)

            elif max_value <= 100:
                # 0~100
                x1 = int((xmin / 100) * w)
                y1 = int((ymin / 100) * h)
                x2 = int((xmax / 100) * w)
                y2 = int((ymax / 100) * h)

            else:
                # 0~1000
                x1 = int((xmin / 1000) * w)
                y1 = int((ymin / 1000) * h)
                x2 = int((xmax / 1000) * w)
                y2 = int((ymax / 1000) * h)

            # -------------------------------------------------
            # 防止越界
            # -------------------------------------------------
            x1 = max(0, min(w - 1, x1))
            y1 = max(0, min(h - 1, y1))
            x2 = max(0, min(w - 1, x2))
            y2 = max(0, min(h - 1, y2))

            if x2 < x1:
                x1, x2 = x2, x1

            if y2 < y1:
                y1, y2 = y2, y1

            mark_type = mark.get("type", "circle")

            # -------------------------------------------------
            # 画圈
            # -------------------------------------------------
            if mark_type == "circle":

                draw.ellipse(
                    [
                        max(0, x1 - 5),
                        max(0, y1 - 5),
                        min(w - 1, x2 + 5),
                        min(h - 1, y2 + 5)
                    ],
                    outline="red",
                    width=4
                )

            # -------------------------------------------------
            # 画叉
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
            # 画框
            # -------------------------------------------------
            elif mark_type == "rectangle":

                draw.rectangle(
                    [x1, y1, x2, y2],
                    outline="red",
                    width=4
                )

            # -------------------------------------------------
            # 默认画圈
            # -------------------------------------------------
            else:

                draw.ellipse(
                    [
                        max(0, x1 - 5),
                        max(0, y1 - 5),
                        min(w - 1, x2 + 5),
                        min(h - 1, y2 + 5)
                    ],
                    outline="red",
                    width=4
                )

        # -------------------------------------------------
        # 7. 保存 PNG
        # -------------------------------------------------
        output = io.BytesIO()

        img.save(
            output,
            format="PNG",
            optimize=True
        )

        output.seek(0)

        # -------------------------------------------------
        # 8. Base64
        # -------------------------------------------------
        image_base64 = base64.b64encode(
            output.getvalue()
        ).decode("utf-8")

        # -------------------------------------------------
        # 9. 返回
        # -------------------------------------------------
        return jsonify({
            "success": True,
            "marked_image_base64": image_base64,
            "marks_count": len(marks),
            "image_width": w,
            "image_height": h
        })

    except Exception as e:

        # -------------------------------------------------
        # 最重要：
        # 把真正的 Python 异常返回给 Dify
        # -------------------------------------------------

        error_detail = traceback.format_exc()

        print(error_detail)

        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": error_detail
        }), 500


# ---------------------------------------------------------
# 本地运行
# ---------------------------------------------------------
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )