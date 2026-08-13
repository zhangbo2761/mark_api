from flask import Flask, request, jsonify, send_from_directory
from PIL import Image, ImageDraw, ImageFont
import io
import os
import json
import uuid
import math
import random
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
    return send_from_directory(IMAGE_DIR, filename)


# =====================================================
# 手写风格绘制函数
# =====================================================

def _jitter(pt, amt=1.5):
    return (
        pt[0] + random.uniform(-amt, amt),
        pt[1] + random.uniform(-amt, amt)
    )


def draw_handwritten_check(draw, x1, y1, x2, y2):
    """
    画绿色手写风格对勾
    """

    w = max(10, x2 - x1)
    h = max(10, y2 - y1)

    cx = x1 + w * 0.5
    cy = y1 + h * 0.5

    p1 = (
        cx - w * 0.35,
        cy
    )

    p2 = (
        cx - w * 0.05,
        cy + h * 0.35
    )

    p3 = (
        cx + w * 0.45,
        cy - h * 0.4
    )

    pts1 = [
        _jitter(p1),
        _jitter(p2)
    ]

    pts2 = [
        _jitter(p2),
        _jitter(p3)
    ]

    # 正确答案使用绿色
    draw.line(
        pts1,
        fill=(0, 160, 0),
        width=5,
        joint="curve"
    )

    draw.line(
        pts2,
        fill=(0, 160, 0),
        width=5,
        joint="curve"
    )


def draw_handwritten_circle(draw, x1, y1, x2, y2):
    """
    画红色手写风格椭圆
    """

    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2

    rx = abs(x2 - x1) / 2 + 10
    ry = abs(y2 - y1) / 2 + 10

    rx = max(5, rx)
    ry = max(5, ry)

    points = []

    steps = 48

    for i in range(steps + 1):

        angle = (i / steps) * 2 * math.pi

        jitter_r = random.uniform(-2, 2)

        px = cx + (rx + jitter_r) * math.cos(angle)
        py = cy + (ry + jitter_r) * math.sin(angle)

        points.append((px, py))

    # 错误答案使用红色
    draw.line(
        points,
        fill=(220, 0, 0),
        width=4,
        joint="curve"
    )


def draw_handwritten_cross(draw, x1, y1, x2, y2):
    """
    画红色 X
    """

    draw.line(
        [(x1, y1), (x2, y2)],
        fill=(220, 0, 0),
        width=4
    )

    draw.line(
        [(x1, y2), (x2, y1)],
        fill=(220, 0, 0),
        width=4
    )


# =====================================================
# 字体
# =====================================================

def _load_font(size):

    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]

    for path in candidates:

        try:

            if os.path.exists(path):

                return ImageFont.truetype(
                    path,
                    size
                )

        except Exception:

            continue

    try:

        return ImageFont.load_default()

    except Exception:

        return None


# =====================================================
# 绘制正确答案
# =====================================================

def draw_correct_answer_text(
    draw,
    x1,
    x2,
    y1,
    y2,
    text,
    img_width,
    img_height
):

    if text is None:
        return

    text = str(text).strip()

    if not text:
        return

    box_h = max(
        1,
        y2 - y1
    )

    font_size = max(
        18,
        int(box_h * 0.9)
    )

    font = _load_font(font_size)

    # 默认放在错误答案右侧
    tx = x2 + 12

    # 默认与答案顶部对齐
    ty = y1 - 2

    # 如果右边空间不够，则放到答案上方
    if tx + 150 > img_width:

        tx = x1

        ty = y2 + 8

    # 防止超出顶部
    if ty < 0:
        ty = 0

    # 防止超出底部
    if ty > img_height - font_size:
        ty = max(0, y1 - font_size - 5)

    try:

        if font:

            draw.text(
                (tx, ty),
                text,
                fill=(220, 0, 0),
                font=font,
                stroke_width=1,
                stroke_fill=(220, 0, 0)
            )

        else:

            draw.text(
                (tx, ty),
                text,
                fill=(220, 0, 0)
            )

    except Exception:

        draw.text(
            (tx, ty),
            text,
            fill=(220, 0, 0)
        )


# =====================================================
# 统一识别 LLM 的批改类型
# =====================================================

def normalize_mark_type(mark):
    """
    将 LLM 各种可能的输出统一转换为：

    check  = 正确
    circle = 错误
    cross  = 错误并画 X
    """

    if not isinstance(mark, dict):
        return None

    # -------------------------------------------------
    # 1. 优先读取 type
    # -------------------------------------------------

    raw_type = mark.get("type")

    if raw_type is not None:

        t = str(raw_type).strip().lower()

        # -----------------------------
        # 正确
        # -----------------------------

        correct_types = {
            "check",
            "correct",
            "right",
            "true",
            "yes",
            "ok",
            "pass",
            "✓",
            "√",
            "对",
            "正确",
            "正确答案"
        }

        if t in correct_types:
            return "check"

        # -----------------------------
        # 错误：画圈
        # -----------------------------

        wrong_circle_types = {
            "circle",
            "wrong",
            "incorrect",
            "error",
            "false",
            "no",
            "fail",
            "×",
            "x",
            "错",
            "错误",
            "错误答案"
        }

        if t in wrong_circle_types:
            return "circle"

        # -----------------------------
        # 错误：画叉
        # -----------------------------

        cross_types = {
            "cross",
            "red_cross",
            "wrong_cross"
        }

        if t in cross_types:
            return "cross"

    # -------------------------------------------------
    # 2. 如果没有明确 type，则检查 is_correct
    # -------------------------------------------------

    if "is_correct" in mark:

        value = mark.get("is_correct")

        if isinstance(value, bool):

            if value:
                return "check"

            return "circle"

        value_str = str(value).strip().lower()

        if value_str in {
            "true",
            "1",
            "yes",
            "correct",
            "right",
            "正确"
        }:
            return "check"

        if value_str in {
            "false",
            "0",
            "no",
            "wrong",
            "incorrect",
            "错误"
        }:
            return "circle"

    # -------------------------------------------------
    # 3. 如果有 correct 字段
    # -------------------------------------------------

    if "correct" in mark:

        value = mark.get("correct")

        if isinstance(value, bool):

            if value:
                return "check"

            return "circle"

    # -------------------------------------------------
    # 4. 如果都无法判断
    #
    # 非常重要：
    # 不再默认画红框
    # -------------------------------------------------

    return None


# =====================================================
# 获取正确答案文字
# =====================================================

def get_correction_text(mark):

    if not isinstance(mark, dict):
        return ""

    possible_fields = [
        "comment",
        "correction",
        "correct_answer",
        "correctAnswer",
        "answer",
        "expected_answer",
        "expectedAnswer"
    ]

    for field in possible_fields:

        value = mark.get(field)

        if value is not None:

            value = str(value).strip()

            if value:
                return value

    return ""


# =====================================================
# 主接口
# =====================================================

@app.route("/mark", methods=["POST"])
def mark_image():

    try:

        # =================================================
        # 1. 获取图片
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

        marks_raw = request.form.get(
            "marks",
            ""
        )

        if not marks_raw:

            marks = []

        else:

            try:

                llm_result = json.loads(
                    marks_raw
                )

                if isinstance(
                    llm_result,
                    dict
                ):

                    marks = llm_result.get(
                        "marks",
                        []
                    )

                elif isinstance(
                    llm_result,
                    list
                ):

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

        if not isinstance(
            marks,
            list
        ):

            marks = []

        # =================================================
        # 4. 打开图片
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
        # 5. 图片尺寸
        # =================================================

        w, h = img.size

        draw = ImageDraw.Draw(img)

        # =================================================
        # 统计
        # =================================================

        check_count = 0
        circle_count = 0
        cross_count = 0
        ignored_count = 0

        debug_marks = []

        # =================================================
        # 6. 处理 marks
        # =================================================

        for mark in marks:

            if not isinstance(
                mark,
                dict
            ):
                ignored_count += 1
                continue

            # -------------------------------------------------
            # 获取坐标
            # -------------------------------------------------

            box = mark.get(
                "box_2d",
                []
            )

            if not isinstance(
                box,
                list
            ):

                ignored_count += 1
                continue

            if len(box) != 4:

                ignored_count += 1
                continue

            try:

                ymin = float(box[0])
                xmin = float(box[1])
                ymax = float(box[2])
                xmax = float(box[3])

            except Exception:

                ignored_count += 1
                continue

            # -------------------------------------------------
            # Gemini / Vision 0~1000 坐标
            # -------------------------------------------------

            x1 = int(
                xmin / 1000 * w
            )

            y1 = int(
                ymin / 1000 * h
            )

            x2 = int(
                xmax / 1000 * w
            )

            y2 = int(
                ymax / 1000 * h
            )

            # -------------------------------------------------
            # 防止越界
            # -------------------------------------------------

            x1 = max(
                0,
                min(w - 1, x1)
            )

            y1 = max(
                0,
                min(h - 1, y1)
            )

            x2 = max(
                0,
                min(w - 1, x2)
            )

            y2 = max(
                0,
                min(h - 1, y2)
            )

            # -------------------------------------------------
            # 坐标纠正
            # -------------------------------------------------

            if x2 < x1:

                x1, x2 = x2, x1

            if y2 < y1:

                y1, y2 = y2, y1

            # -------------------------------------------------
            # 识别类型
            # -------------------------------------------------

            mark_type = normalize_mark_type(
                mark
            )

            correction = get_correction_text(
                mark
            )

            # -------------------------------------------------
            # Debug 信息
            # -------------------------------------------------

            debug_marks.append({
                "original_type": mark.get("type"),
                "is_correct": mark.get("is_correct"),
                "normalized_type": mark_type,
                "comment": correction,
                "box_2d": box
            })

            # =================================================
            # 正确 → 绿色 ✓
            # =================================================

            if mark_type == "check":

                draw_handwritten_check(
                    draw,
                    x1,
                    y1,
                    x2,
                    y2
                )

                check_count += 1

            # =================================================
            # 错误 → 红圈 + 正确答案
            # =================================================

            elif mark_type == "circle":

                draw_handwritten_circle(
                    draw,
                    x1,
                    y1,
                    x2,
                    y2
                )

                draw_correct_answer_text(
                    draw,
                    x1,
                    x2,
                    y1,
                    y2,
                    correction,
                    w,
                    h
                )

                circle_count += 1

            # =================================================
            # 错误 → 红叉
            # =================================================

            elif mark_type == "cross":

                draw_handwritten_cross(
                    draw,
                    x1,
                    y1,
                    x2,
                    y2
                )

                # 如果存在正确答案，也写出来
                if correction:

                    draw_correct_answer_text(
                        draw,
                        x1,
                        x2,
                        y1,
                        y2,
                        correction,
                        w,
                        h
                    )

                cross_count += 1

            # =================================================
            # 无法判断
            #
            # 不再画红框！
            #
            # 这是这次修改最重要的一点
            # =================================================

            else:

                ignored_count += 1

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
        # 9. 返回结果
        # =================================================

        return jsonify({

            "success": True,

            "marked_image_url":
                image_url,

            "marks_count":
                len(marks),

            "check_count":
                check_count,

            "circle_count":
                circle_count,

            "cross_count":
                cross_count,

            "ignored_count":
                ignored_count,

            "image_width":
                w,

            "image_height":
                h,

            # 调试信息
            # 方便确认 LLM 到底返回了什么
            "debug_marks":
                debug_marks
        })

    except Exception as e:

        error_detail = traceback.format_exc()

        print(error_detail)

        return jsonify({

            "success": False,

            "error":
                str(e),

            "traceback":
                error_detail

        }), 500


# =====================================================
# 启动
# =====================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
    )