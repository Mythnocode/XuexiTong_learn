import html
import json
import re
import time

import requests


MOOC_HOST = "https://mooc1.chaoxing.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36"
)


def _headers(cookie, referer=None):
    return {
        "Cookie": cookie,
        "User-Agent": USER_AGENT,
        "Referer": referer or f"{MOOC_HOST}/",
    }


def _extract_json_after(text, marker):
    match = re.search(re.escape(marker) + r"\s*=\s*\{", text)
    if not match:
        return None
    start = match.end() - 1

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:index + 1])
    return None


def get_chapters(cookie, course_id, clazz_id, cpi):
    url = f"{MOOC_HOST}/mycourse/studentstudycourselist"
    params = {
        "courseId": course_id,
        "clazzid": clazz_id,
        "cpi": cpi,
        "mooc2": 1,
    }
    response = requests.get(
        url,
        params=params,
        headers=_headers(
            cookie,
            f"{MOOC_HOST}/mooc-ans/mycourse/studentstudy"
            f"?courseId={course_id}&clazzid={clazz_id}&cpi={cpi}",
        ),
        timeout=20,
    )
    response.raise_for_status()

    pattern = re.compile(
        r'<span class="posCatalog_name"[^>]*title="([^"]*)"[^>]*'
        r"getTeacherAjax\(\s*'[^']*'\s*,\s*'[^']*'\s*,\s*'(\d+)'\s*\)"
    )
    chapters = []
    for title, knowledge_id in pattern.findall(response.text):
        chapters.append({
            "title": html.unescape(title).strip(),
            "knowledge_id": knowledge_id,
        })
    return chapters


def get_card_args(cookie, course_id, clazz_id, cpi, knowledge_id, cache_bust=False):
    url = f"{MOOC_HOST}/mooc-ans/knowledge/cards"
    params = {
        "clazzid": clazz_id,
        "courseid": course_id,
        "knowledgeid": knowledge_id,
        "num": 0,
        "ut": "s",
        "cpi": cpi,
        "v": "2025-0424-1038-4",
        "mooc2": 1,
        "isMicroCourse": "false",
        "editorPreview": 0,
    }
    if cache_bust:
        params["_t"] = int(time.time() * 1000)
    response = requests.get(
        url,
        params=params,
        headers=_headers(
            cookie,
            f"{MOOC_HOST}/mooc-ans/mycourse/studentstudy"
            f"?courseId={course_id}&clazzid={clazz_id}&cpi={cpi}",
        ),
        timeout=20,
    )
    response.raise_for_status()
    card_args = _extract_json_after(response.text, "mArg")
    if card_args is not None:
        # 人脸/章节抓拍是否真正生效取决于页面里有没有遮罩节点，
        # 只看 mArg 的 chapterCapture / videoFaceCaptureEnc 会误判。
        card_args["__page_flags__"] = {
            "hasFaceMask": bool(
                re.search(r'class="[^"]*\bmaskDiv1\b', response.text)
            ),
            "hasChapterFaceMask": (
                "chapterVideoFaceMaskDiv" in response.text
                or "chapterVideoFaceQrMaskDiv" in response.text
            ),
            "hasFaceQrMask": "chapterVideoFaceQrMaskDiv" in response.text,
        }
    return card_args


def get_video_status(cookie, object_id, fid):
    url = f"{MOOC_HOST}/ananas/status/{object_id}"
    response = requests.get(
        url,
        params={"k": fid, "flag": "normal", "ro": 0},
        headers=_headers(cookie, f"{MOOC_HOST}/ananas/modules/video/index.html"),
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def build_video(cookie, card_args, attachment):
    defaults = card_args.get("defaults") or {}
    status = get_video_status(
        cookie,
        attachment["objectId"],
        defaults.get("fid") or defaults.get("cFid") or "",
    )
    if status.get("status") != "success":
        return None

    duration = int(status.get("duration") or attachment.get("attDuration") or 0)
    report_url = defaults["reportUrl"].rstrip("/")

    return {
        "url": f'{report_url}/{status["dtoken"]}',
        "clazzId": str(defaults["clazzId"]),
        "userid": str(defaults["userid"]),
        "jobid": str(attachment["jobid"]),
        "objectId": attachment["objectId"],
        "duration": duration,
        "clipTime": f"0_{duration}",
        "otherInfo": attachment["otherInfo"],
        "courseId": str(defaults["courseid"]),
        "attDuration": int(attachment.get("attDuration") or duration),
        "attDurationEnc": attachment.get("attDurationEnc", ""),
        "videoFaceCaptureEnc": attachment.get("videoFaceCaptureEnc", ""),
        "report_interval": int(defaults.get("reportTimeInterval") or 60),
    }


def get_course_videos(cookie, course_id, clazz_id, cpi):
    videos = []
    chapters = get_chapters(cookie, course_id, clazz_id, cpi)
    for chapter_index, chapter in enumerate(chapters, 1):
        card_args = get_card_args(
            cookie,
            course_id,
            clazz_id,
            cpi,
            chapter["knowledge_id"],
        )
        if not card_args:
            continue
        chapter_videos = [
            attachment
            for attachment in card_args.get("attachments") or []
            if attachment.get("type") == "video" and attachment.get("objectId")
        ]
        for video_index, attachment in enumerate(chapter_videos, 1):
            video = build_video(cookie, card_args, attachment)
            if video:
                property_info = attachment.get("property")
                video_name = (
                    property_info.get("name", "")
                    if isinstance(property_info, dict)
                    else ""
                )
                videos.append({
                    "chapter_index": chapter_index,
                    "video_index": video_index,
                    "video_count": len(chapter_videos),
                    "title": chapter["title"],
                    "video_name": video_name,
                    "knowledge_id": chapter["knowledge_id"],
                    "is_passed": attachment.get("isPassed"),
                    "play_time": attachment.get("playTime", 0) // 1000,
                    "VIDEO": video,
                    # 保留原始配置，便于在 main.py 里和同课程其他视频对比。
                    "card_args": card_args,
                    "attachment": attachment,
                })
    return videos


def get_video_state(cookie, course_id, clazz_id, cpi, knowledge_id, object_id=None):
    card_args = get_card_args(
        cookie, course_id, clazz_id, cpi, knowledge_id, cache_bust=True
    )
    for attachment in (card_args or {}).get("attachments") or []:
        if attachment.get("type") != "video" or not attachment.get("objectId"):
            continue
        if object_id and attachment.get("objectId") != object_id:
            continue
        return {
            "is_passed": bool(attachment.get("isPassed")),
            "play_time": int(attachment.get("playTime") or 0) // 1000,
            "card_args": card_args,
            "attachment": attachment,
        }
    return {
        "is_passed": False,
        "play_time": 0,
        "card_args": card_args,
        "attachment": None,
    }
