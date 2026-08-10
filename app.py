from flask import Flask, request, jsonify
from PIL import Image, ImageDraw
import io
import os
import json
import uuid
import traceback

app = Flask(__name__)

IMAGE_DIR = "/tmp/marked_images"
os.makedirs(IMAGE_DIR, exist_ok=True)


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ok",
        "message": "Mark API is running",
        "endpoint": "/mark"
    })


@app.route("/images/<filename>", methods=["GET"])
def get_image(filename):
    from flask import send_from_directory

    return send_from_directory(
        IMAGE_DIR,
        filename
    )


@app.route("/mark", methods=["POST"])
def mark_image():

    try:

        # =================================================
        # 1. 获取图片文件
        # =================================================

        image_file = request.files.get("image")

        if image_file is None:
            return jsonify({
                "success": False,
                "error": "没有收到 image 文件",
                "received_files": list(request.files.keys())
            }), 400

        # =================================================
        # 2. 获取 LLM marks
        # =================================================

        marks_raw = request.form.get("marks", "")

        if not marks_raw:
            marks = []

        else:

            try:
                llm_result = json.loads(marks_raw)

                # LLM正常格式：
                #
                # {
                #   "marks": [...],
                #   "encouragement": "...",
                #   ...
                # }

                if isinstance(llm_result, dict):
                    marks = llm_result.get("marks", [])

                elif isinstance(llm_result, list):
                    marks = llm_result

                else:
                    marks = []

            except Exception as e:

                return jsonify({
                    "success": False,
                    "error": "LLM返回的JSON无法解析",
                    "detail": str(e),
                    "marks_raw": marks_raw
                }), 400

        # =================================================
        # 3. 确保 marks 是 list
        # =================================================

        if not isinstance(marks, list):
            marks = []

        # =================================================
        # 4. 打开上传图片
        # =================================================

        try:

            image_bytes = image_file.read()

            img = Image.open(
                io.BytesIO(image_bytes)
            ).convert("RGB")

            img.load()

        except Exception as e:

            return jsonify({
                "success": False,
                "error": "无法解析上传的图片",
                "detail": str(e)
            }), 400

        # =================================================
        # 5. 获取尺寸
        # =================================================

        w, h = img.size

        draw = ImageDraw.Draw(img)

        # =================================================
        # 6. 处理 marks
        # =================================================

        for mark in marks:

            if not isinstance(mark, dict):
                continue

            box = mark.get("box_2d", [])

            if not isinstance(box, list):
                continue

            if len(box) != 4:
                continue

            try:

                ymin = float(box[0])
                xmin = float(box[1])
                ymax = float(box[2])
                xmax = float(box[3])

            except Exception:

                continue

            # =================================================
            # 你的 LLM 使用 0~1 坐标
            # =================================================

            x1 = int(xmin * w)
            y1 = int(ymin * h)

            x2 = int(xmax * w)
            y2 = int(ymax * h)

            # =================================================
            # 防止越界
            # =================================================

            x1 = max(0, min(w - 1, x1))
            y1 = max(0, min(h - 1, y1))

            x2 = max(0, min(w - 1, x2))
            y2 = max(0, min(h - 1, y2))

            if x2 < x1:
                x1, x2 = x2, x1

            if y2 < y1:
                y1, y2 = y2, y1

            # =================================================
            # 类型
            # =================================================

            mark_type = mark.get(
                "type",
                "circle"
            )

            # =================================================
            # 画红圈
            # =================================================

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

            # =================================================
            # 红叉
            # =================================================

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

            # =================================================
            # 默认红框
            # =================================================

            else:

                draw.rectangle(
                    [x1, y1, x2, y2],
                    outline="red",
                    width=4
                )

        # =================================================
        # 7. 保存图片
        # =================================================

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

        # =================================================
        # 8. 图片 URL
        # =================================================

        image_url = (
            request.host_url.rstrip("/")
            + "/images/"
            + filename
        )

        # =================================================
        # 9. 返回
        # =================================================

        return jsonify({
            "success": True,
            "marked_image_url": image_url,
            "marks_count": len(marks),
            "image_width": w,
            "image_height": h
        })

    except Exception as e:

        error_detail = traceback.format_exc()

        print(error_detail)

        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": error_detail
        }), 500


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
    )