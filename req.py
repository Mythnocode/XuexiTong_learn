import argparse
import hashlib
import time

import requests

from getVideo import get_course_videos


SALT = "d_yHJ!$pdA~5"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36 Edg/155.0.0.0"
)


def load_video(cookie, course_id, clazz_id, cpi, knowledge_id=None, title=None):
    videos = get_course_videos(cookie, course_id, clazz_id, cpi)
    if knowledge_id:
        matched = [v for v in videos if v["knowledge_id"] == str(knowledge_id)]
    elif title:
        matched = [v for v in videos if title in v["title"]]
    else:
        raise ValueError("需要指定 knowledge_id 或 title")

    if not matched:
        raise LookupError("没有找到匹配的视频")
    if len(matched) > 1 and title and not knowledge_id:
        names = "\n".join(f"  {v['knowledge_id']}  {v['title']}" for v in matched)
        raise LookupError(f"标题匹配到多个视频，请改用 knowledge_id：\n{names}")
    return matched[0]


def make_enc(video, playing_time):
    raw = (
        f"[{video['clazzId']}][{video['userid']}][{video['jobid']}][{video['objectId']}]"
        f"[{int(playing_time) * 1000}][{SALT}]"
        f"[{int(video['duration']) * 1000}][{video['clipTime']}]"
    )
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def send_heartbeat(video, cookie, playing_time, isdrag="0", debug=False):
    headers = {
        "User-Agent": USER_AGENT,
        "Cookie": cookie,
        "Referer": "https://mooc1.chaoxing.com/ananas/modules/video/index.html",
        "Accept": "*/*",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
    }
    other_info = str(video.get("otherInfo") or "")
    course_query = ""
    course_id = str(video.get("courseId") or "")
    if course_id and f"courseId={course_id}" not in other_info:
        course_query = f"&courseId={course_id}"

    query = (
        f"clazzId={video['clazzId']}"
        f"&playingTime={playing_time}"
        f"&duration={video['duration']}"
        f"&clipTime={video['clipTime']}"
        f"&objectId={video['objectId']}"
        f"&otherInfo={other_info}{course_query}"
        f"&jobid={video['jobid']}"
        f"&userid={video['userid']}"
        f"&isdrag={isdrag}"
        f"&view=pc"
        f"&enc={make_enc(video, playing_time)}"
        f"&rt=0.9"
        f"&videoFaceCaptureEnc={video['videoFaceCaptureEnc']}"
        f"&dtype=Video"
        f"&_t={int(time.time() * 1000)}"
        f"&attDuration={video['attDuration']}"
        f"&attDurationEnc={video['attDurationEnc']}"
        f"&courseEngineInfo=false"
    )
    url = f"{video['url']}?{query}"
    if debug:
        print(f"[debug] {url}")
    response = requests.get(
        url,
        headers=headers,
        timeout=10,
    )
    if response.status_code == 302:
        print("被重定向，可能触发风控:", response.headers.get("Location"))
        return None
    try:
        return response.json()
    except ValueError:
        print("非 JSON 响应:", response.status_code, response.text[:200])
        return None


def report_realtime(video, cookie, start=0, interval=None, debug=False):
    end = int(video["duration"])
    position = min(max(0, int(start)), end)
    interval = max(1, int(interval or video.get("report_interval") or 60))
    limit = int(video.get("report_interval") or 0)
    if limit and interval > limit:
        print(f"上报间隔 {interval}s 超过课程设置的 {limit}s，自动改为 {limit}s")
        interval = limit
    if position >= end:
        # 真实播放器会把已到结尾的 playTime 重置为 0，否则 isdrag=3 之后
        # 再上报同一个 playingTime，服务端不会累计有效观看时长。
        print(f"服务端记录位置已到结尾（{position}s），按播放器逻辑从 0 重新开始")
        position = 0

    return replay_range(
        video,
        cookie,
        position,
        end,
        interval,
        debug=debug,
    )


def replay_range(video, cookie, start, end, step, debug=False, label=""):
    """按真实时间重放 [start, end]，返回服务端是否判定通过。"""
    duration = int(video["duration"])
    start = max(0, min(int(start), duration))
    end = max(0, min(int(end), duration))
    step = max(1, int(step))
    prefix = f"{label} " if label else ""
    if start >= end:
        return False

    # 真实播放器按下播放时会先发一次 isdrag=3，服务端靠它开启本次学习会话。
    # 只发 isdrag=0 的心跳时，服务端可能整段丢弃。
    response = send_heartbeat(video, cookie, start, "3", debug=debug)
    print(f"{prefix}play playingTime={start}, resp={response}")
    if response is None:
        return False
    if response.get("isPassed"):
        print("已完成")
        return True

    position = start
    last_report = time.monotonic()
    while position < end:
        remaining = step - (time.monotonic() - last_report)
        if remaining > 0:
            time.sleep(remaining)
        last_report = time.monotonic()
        position = min(end, position + step)

        response = send_heartbeat(video, cookie, position, "0", debug=debug)
        print(f"{prefix}playingTime={position}, resp={response}")
        if response is None:
            return False
        if response.get("isPassed"):
            print("已完成")
            return True
        if response.get("videoTimeLimit"):
            print("服务端提示：本次学习时长已达上限，进度不会被记录")
        if response.get("hasJobLimit"):
            print("服务端提示：任务点数量已达上限，进度不会被记录")

    response = send_heartbeat(video, cookie, end, "4", debug=debug)
    print(f"{prefix}final playingTime={end}, resp={response}")
    return bool(response and response.get("isPassed"))


def finish_video(video, cookie, debug=False):
    """到结尾仍未通过时，补发一次 playing + ended，触发服务端结算。"""
    end = int(video["duration"])
    for isdrag in ("0", "4"):
        response = send_heartbeat(video, cookie, end, isdrag, debug=debug)
        print(f"[finish] isdrag={isdrag} playingTime={end}, resp={response}")
        if response and response.get("isPassed"):
            return True
    return False


def parse_args():
    parser = argparse.ArgumentParser(description="按实际播放进度上报单个视频")
    parser.add_argument("--cookie", required=True, help="学习通整站 Cookie")
    parser.add_argument("--course", required=True, help="courseId")
    parser.add_argument("--clazz", required=True, help="clazzId")
    parser.add_argument("--cpi", required=True, help="cpi")
    parser.add_argument("--knowledge", help="knowledgeId，优先使用")
    parser.add_argument("--title", help="章节标题关键字，唯一匹配时使用")
    parser.add_argument("--time", type=int, default=0, help="当前实际播放到的秒数")
    parser.add_argument("--isdrag", default="0", help="0 正常播放，4 播放结束")
    parser.add_argument("--realtime", action="store_true", help="按真实时间持续上报")
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="上报间隔秒数，默认使用 mArg 里的 reportTimeInterval（通常 60）",
    )
    parser.add_argument("--debug", action="store_true", help="打印完整请求 URL")
    parser.add_argument(
        "--finish",
        action="store_true",
        help="只发送结尾结算请求（playing + ended），不重新计时",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    item = load_video(
        args.cookie,
        args.course,
        args.clazz,
        args.cpi,
        knowledge_id=args.knowledge,
        title=args.title,
    )
    video = item["VIDEO"]
    print(f"{item['knowledge_id']}  {item['title']}  {video['duration']}s")

    if item.get("is_passed"):
        print("该视频已标记完成，无需上报")
        return

    if args.finish:
        end = args.time if args.time is not None else int(video["duration"])
        for isdrag in ("0", "4"):
            response = send_heartbeat(
                video,
                args.cookie,
                end,
                isdrag,
                debug=args.debug,
            )
            print(f"[finish] isdrag={isdrag} playingTime={end}, resp={response}")
            if response and response.get("isPassed"):
                print("已完成")
                return
    elif args.realtime:
        report_realtime(
            video,
            args.cookie,
            args.time,
            args.interval,
            debug=args.debug,
        )
    else:
        response = send_heartbeat(
            video,
            args.cookie,
            args.time,
            args.isdrag,
            debug=args.debug,
        )
        print(f"playingTime={args.time}, resp={response}")


if __name__ == "__main__":
    main()
