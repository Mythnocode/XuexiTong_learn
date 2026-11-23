import json

from getClass import get_class_list
from getVideo import get_course_videos, get_video_state
from req import finish_video, replay_range, report_realtime


def choose(items, render):
    for index, item in enumerate(items, 1):
        print(f"  [{index}] {render(item)}")
    while True:
        raw = input(
            "请输入编号，或直接输入 knowledgeId/文件名（q 退出）: "
        ).strip().lower()
        if raw in {"q", "quit", "exit"}:
            return None
        if not raw:
            print("编号无效，请重新输入")
            continue
        if raw.isdigit():
            index = int(raw)
            if 1 <= index <= len(items):
                return items[index - 1]
        matches = [
            item
            for item in items
            if str(item.get("knowledge_id") or "").lower() == raw
            or raw in str(item.get("video_name") or "").lower()
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            print("匹配到多个，请改用编号选择：")
            for item in matches[:10]:
                print(f"  {item.get('knowledge_id')}  {video_label(item)}")
            continue
        print("编号无效，请重新输入")


def video_label(item):
    name = str(item.get("video_name") or "").strip()
    return name[:50]


def position_label(item):
    chapter = item.get("chapter_index")
    video_index = item.get("video_index")
    video_count = item.get("video_count")
    if chapter and video_index and video_count:
        return f"章{chapter} 视频{video_index}/{video_count}"
    return ""


def format_progress(item):
    duration = item["VIDEO"]["duration"]
    played = min(item["play_time"], duration)
    status = "已完成" if item["is_passed"] else "未完成"
    label = video_label(item)
    suffix = f"  {label}" if label else ""
    position = position_label(item)
    position_suffix = f"  [{position}]" if position else ""
    return (
        f"{item['knowledge_id']}  {item['title']}{position_suffix}{suffix}"
        f"  [{status}]  {played}/{duration}s"
    )


def ask_int(prompt, default, minimum):
    while True:
        raw = input(prompt).strip()
        if raw == "":
            return default
        try:
            value = int(raw)
        except ValueError:
            print("请输入整数")
            continue
        if value >= minimum:
            return value
        print(f"不能小于 {minimum}")


def refresh_state(cookie, course, item):
    state = get_video_state(
        cookie,
        course["course_id"],
        course["id"],
        course["cpi"],
        item["knowledge_id"],
        object_id=item["VIDEO"]["objectId"],
    )
    item["is_passed"] = state["is_passed"]
    item["play_time"] = state["play_time"]
    if state.get("card_args"):
        item["card_args"] = state["card_args"]
    if state.get("attachment"):
        item["attachment"] = state["attachment"]
    return state


def _flag(value):
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true"}
    return bool(value)


def _as_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except ValueError:
            return [value]
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
    return []


def _meta(attachment, defaults, card_args, key, default=None):
    for source in (attachment, defaults, card_args):
        if not source:
            continue
        value = source.get(key)
        if value not in (None, ""):
            return value
    return default


def lesson_profile(item):
    video = item["VIDEO"]
    card_args = item.get("card_args") or {}
    attachment = item.get("attachment") or {}
    defaults = card_args.get("defaults") or {}

    def pick(key, default=None):
        return _meta(attachment, defaults, card_args, key, default)

    def pick_default(key, default=None):
        for source in (defaults, card_args, attachment):
            if not source:
                continue
            value = source.get(key)
            if value not in (None, ""):
                return value
        return default

    duration = int(video.get("duration") or 0)
    attachments = card_args.get("attachments") or []
    page_flags = card_args.get("__page_flags__") or {}
    non_video = [
        attachment
        for attachment in attachments
        if attachment.get("type") != "video" or not attachment.get("objectId")
    ]
    return {
        "duration": duration,
        "userid": str(video.get("userid") or ""),
        "clazzId": str(video.get("clazzId") or ""),
        "courseId": str(video.get("courseId") or ""),
        "attDuration": int(pick("attDuration", duration) or duration),
        "begins": int(pick("begins", 0) or 0),
        "ends": int(pick("ends", 0) or 0),
        "playTime": int(pick("playTime", 0) or 0) // 1000,
        "headOffset": int(pick("headOffset", 0) or 0) // 1000,
        "reportInterval": int(
            pick_default("reportTimeInterval", 60) or 60
        ),
        "chapterCapture": int(pick_default("chapterCapture", 0) or 0),
        "chapterCollectionType": int(
            pick_default("chapterCollectionType", 0) or 0
        ),
        "silentFaceCapture": int(
            pick_default("silentFaceCapture", 0) or 0
        ),
        "startCapture": int(pick_default("startCapture", 0) or 0),
        "endCapture": int(pick_default("endCapture", 0) or 0),
        "playingCapture": int(pick_default("playingCapture", 0) or 0),
        "playingLoopCapture": int(
            pick_default("playingLoopCapture", 0) or 0
        ),
        "playAginCapture": int(pick_default("playAginCapture", 0) or 0),
        "captureInterval": int(pick_default("captureInterval", 0) or 0),
        "randomCaptureTime": int(pick("randomCaptureTime", 0) or 0),
        "randomFaceCaptureTimeList": _as_list(
            pick("randomFaceCaptureTimeList", [])
        ),
        "supportHeartbeat": _flag(pick_default("supportHeartbeat", False)),
        "supportVideoPluginV1": _flag(
            pick_default("supportVideoPluginV1", False)
        ),
        "eventArray": _as_list(pick_default("eventArray", [])),
        "isFiled": str(pick_default("isFiled", "0")),
        "state": str(pick_default("state", "0")),
        "isSupportFace": _flag(pick_default("isSupportFace", False)),
        "isShowFaceCollection": _flag(
            pick_default("isShowFaceCollection", False)
        ),
        "videoFaceCaptureEnc": str(attachment.get("videoFaceCaptureEnc") or ""),
        "pageFlags": page_flags,
        "hasFaceMask": bool(page_flags.get("hasFaceMask")),
        "hasChapterFaceMask": bool(page_flags.get("hasChapterFaceMask")),
        "hasFaceQrMask": bool(page_flags.get("hasFaceQrMask")),
        "attDurationEnc": str(attachment.get("attDurationEnc") or ""),
        "otherInfo": str(attachment.get("otherInfo") or ""),
        "jobid": str(attachment.get("jobid") or ""),
        "objectId": str(
            attachment.get("objectId") or video.get("objectId") or ""
        ),
        "attachments": attachments,
        "nonVideoAttachments": non_video,
    }


def print_diagnostics(item, state):
    card_args = state.get("card_args") or item.get("card_args") or {}
    attachment = state.get("attachment") or item.get("attachment") or {}
    defaults = card_args.get("defaults") or {}
    profile = lesson_profile(item)

    print("\n视频上报参数检查：")
    position = position_label(item)
    if position:
        print(f"  章节定位：{position}  {video_label(item)}")
    print(
        f"  reportTimeInterval={profile['reportInterval']}s  "
        f"playTime={profile['playTime']}s  headOffset={profile['headOffset']}s  "
        f"attDuration={profile['attDuration']}s  duration={profile['duration']}s"
    )
    print(
        f"  begins={profile['begins']}  ends={profile['ends']}  "
        f"jobid={profile['jobid']}  objectId={profile['objectId']}"
    )
    print(
        f"  userid={profile['userid']}  clazzId={profile['clazzId']}  "
        f"courseId={profile['courseId']}"
    )
    print(
        f"  supportHeartbeat={profile['supportHeartbeat']}  "
        f"supportVideoPluginV1={profile['supportVideoPluginV1']}  "
        f"chapterCapture={profile['chapterCapture']}  "
        f"isSupportFace={profile['isSupportFace']}(mArg)  "
        f"isShowFaceCollection={profile['isShowFaceCollection']}(mArg)"
    )
    print(
        f"  chapterCollectionType={profile['chapterCollectionType']}  "
        f"silentFaceCapture={profile['silentFaceCapture']}  "
        f"captureInterval={profile['captureInterval']}  "
        f"startCapture={profile['startCapture']}  endCapture={profile['endCapture']}"
    )
    print(
        f"  playingCapture={profile['playingCapture']}  "
        f"playingLoopCapture={profile['playingLoopCapture']}  "
        f"playAginCapture={profile['playAginCapture']}  "
        f"randomCaptureTime={profile['randomCaptureTime']}  "
        f"randomFaceCaptureTimeList={profile['randomFaceCaptureTimeList']}"
    )
    print(
        f"  isFiled={profile['isFiled']}  state={profile['state']}  "
        f"attDurationEnc={'有' if profile['attDurationEnc'] else '无'}  "
        f"videoFaceCaptureEnc={'有' if profile['videoFaceCaptureEnc'] else '无'}  "
        f"eventArray={'有(%d)' % len(profile['eventArray']) if profile['eventArray'] else '无'}"
    )
    print(
        f"  页面抓拍节点：maskDiv1={profile['hasFaceMask']}  "
        f"章节人脸遮罩={profile['hasChapterFaceMask']}  "
        f"二维码遮罩={profile['hasFaceQrMask']}"
    )
    if profile["nonVideoAttachments"]:
        summary = ", ".join(
            f"{attachment.get('type') or '?'}"
            f"({attachment.get('objectId') or '-'})"
            for attachment in profile["nonVideoAttachments"][:6]
        )
        print(
            f"  同章节其他任务点：{len(profile['nonVideoAttachments'])} 个  "
            f"{summary}"
        )
    else:
        print("  同章节其他任务点：无")

    if profile["attachments"]:
        print("  本章节附件清单（* 为脚本当前使用的视频）：")
        for index, attachment in enumerate(profile["attachments"], 1):
            property_info = attachment.get("property")
            if not isinstance(property_info, dict):
                property_info = {}
            mark = "*" if attachment.get("objectId") == profile["objectId"] else " "
            name = str(property_info.get("name") or "")[:60]
            play_time = int(attachment.get("playTime") or 0) // 1000
            print(
                f"   {mark}{index}. type={attachment.get('type') or '?'}  "
                f"objectId={attachment.get('objectId') or '-'}  "
                f"jobid={attachment.get('jobid') or '-'}  "
                f"dur={attachment.get('attDuration') or '-'}  "
                f"play={play_time}s  "
                f"passed={bool(attachment.get('isPassed'))}  {name}"
            )

    blockers = []
    warnings = []
    if profile["supportHeartbeat"] or profile["supportVideoPluginV1"]:
        blockers.append(
            "课程启用了播放器事件/心跳校验（eventArray），纯 HTTP 心跳可能不被记录"
        )
    if profile["chapterCapture"] > 0:
        if profile["hasFaceMask"] or profile["hasChapterFaceMask"]:
            blockers.append(
                "chapterCapture=1 且页面确实有人脸采集遮罩："
                "播放器会先抓拍再上报，纯 HTTP 心跳无法替代"
            )
        else:
            warnings.append(
                "chapterCapture=1，但页面 HTML 里没检测到人脸遮罩；"
                "可能只是章节学习日志，不一定会拦住视频任务点"
            )
    if profile["randomFaceCaptureTimeList"] or profile["randomCaptureTime"] > 0:
        if profile["chapterCapture"] and (
            profile["hasFaceMask"] or profile["hasChapterFaceMask"]
        ):
            blockers.append(
                "配置了随机人脸抓拍时间点，且 chapterCapture=1，"
                "播放器会在指定时间要求抓拍"
            )
        else:
            warnings.append(
                "配置了随机人脸抓拍时间点，但页面没有生效的抓拍遮罩，"
                "通常不触发"
            )
    if profile["isFiled"] == "1" or profile["state"] == "1":
        blockers.append("附件 isFiled=1 或 state=1，播放器本身会跳过上报")
    if profile["begins"] or profile["ends"]:
        blockers.append(
            f"这是裁剪视频（begins={profile['begins']}, "
            f"ends={profile['ends']}），"
            "当前 clipTime 仍按完整视频计算"
        )
    if profile["attDuration"] != profile["duration"]:
        blockers.append(
            f"attDuration({profile['attDuration']}s) 与 "
            f"duration({profile['duration']}s) 不一致，"
            "签名或完成判定可能对不上"
        )
    if profile["nonVideoAttachments"]:
        blockers.append(
            f"本章节还有 {len(profile['nonVideoAttachments'])} 个非视频任务点，"
            "章节完成可能要一起做"
        )
    if profile["otherInfo"]:
        node_marker = f"nodeId_{item['knowledge_id']}"
        cpi = str(defaults.get("cpi") or "")
        if node_marker not in profile["otherInfo"]:
            blockers.append(
                "otherInfo 里的 nodeId 与当前章节不一致，可能是缓存/配置错位"
            )
        if cpi and f"cpi_{cpi}" not in profile["otherInfo"]:
            blockers.append("otherInfo 里的 cpi 与当前班级不一致")
    if profile["duration"] >= 1200:
        warnings.append(
            "视频不短于 20 分钟；若课程有单次学习时长上限，"
            "建议分段观看并留出休息时间"
        )
    for warning in blockers:
        print(f"  [!] {warning}")
    for warning in warnings:
        print(f"  [i] {warning}")
    if not blockers:
        print("  [ok] 未发现课程级拦截标记")
    return blockers


COMPARE_FIELDS = [
    ("reportInterval", "上报间隔"),
    ("chapterCapture", "章节抓拍"),
    ("chapterCollectionType", "抓拍类型"),
    ("silentFaceCapture", "静默抓拍"),
    ("startCapture", "开始抓拍"),
    ("endCapture", "结束抓拍"),
    ("playingCapture", "播放抓拍"),
    ("playingLoopCapture", "循环抓拍"),
    ("playAginCapture", "重播抓拍"),
    ("captureInterval", "抓拍间隔"),
    ("randomCaptureTime", "随机抓拍时间"),
    ("hasFaceMask", "页面人脸遮罩"),
    ("hasChapterFaceMask", "章节人脸遮罩"),
    ("supportHeartbeat", "播放器心跳校验"),
    ("supportVideoPluginV1", "播放器插件校验"),
    ("isFiled", "isFiled"),
    ("state", "state"),
]


def print_comparison(videos, selected):
    if len(videos) < 2:
        return

    profiles = [lesson_profile(item) for item in videos]
    selected_profile = lesson_profile(selected)

    print(f"\n同课程视频配置对比（共 {len(videos)} 个，* 为当前视频）：")
    for index, (item, profile) in enumerate(zip(videos, profiles), 1):
        mark = "*" if item is selected else " "
        face = "有" if profile["hasFaceMask"] or profile["hasChapterFaceMask"] else "无"
        random_flag = (
            "随机"
            if profile["randomFaceCaptureTimeList"]
            or profile["randomCaptureTime"] > 0
            else "-"
        )
        passed = "已完成" if item["is_passed"] else "未完成"
        print(
            f" {mark}[{index:>2}] {item['knowledge_id']}  "
            f"{profile['duration']:>4}s  int={profile['reportInterval']:>2}  "
            f"cap={profile['chapterCapture']}  {random_flag:<2}  face={face}  "
            f"{passed}  {min(item['play_time'], profile['duration'])}/"
            f"{profile['duration']}"
        )

    differences = []
    for key, label in COMPARE_FIELDS:
        others = [
            profile[key]
            for index, profile in enumerate(profiles)
            if videos[index] is not selected
        ]
        if others and selected_profile[key] not in others:
            values = sorted({str(value) for value in others})
            suffix = " ..." if len(values) > 4 else ""
            differences.append(
                f"{label}: 当前={selected_profile[key]}，"
                f"其他={','.join(values[:4])}{suffix}"
            )

    selected_random = bool(
        selected_profile["randomFaceCaptureTimeList"]
        or selected_profile["randomCaptureTime"] > 0
    )
    other_random = any(
        profile["randomFaceCaptureTimeList"] or profile["randomCaptureTime"] > 0
        for index, profile in enumerate(profiles)
        if videos[index] is not selected
    )
    if selected_random != other_random:
        differences.append(
            f"随机人脸抓拍: 当前={'有' if selected_random else '无'}，"
            f"其他={'有' if other_random else '无'}"
        )

    print("\n与同课程其他视频相比：")
    if differences:
        for difference in differences:
            print(f"  - {difference}")
    else:
        print("  - 未发现配置项差异")

    special = []
    if selected_profile["chapterCapture"] > 0 and (
        selected_profile["hasFaceMask"] or selected_profile["hasChapterFaceMask"]
    ):
        special.append(
            "chapterCapture=1 且页面存在抓拍遮罩：播放器会要求人脸/章节抓拍，"
            "纯 HTTP 心跳无法替代"
        )
    if selected_random:
        special.append(
            "存在随机抓拍时间点：真实播放器会在指定时间弹出人脸采集"
        )
    if selected_profile["nonVideoAttachments"]:
        special.append(
            f"本章节还有 {len(selected_profile['nonVideoAttachments'])} 个"
            "非视频任务点，章节完成条件可能不止视频"
        )
    if selected_profile["otherInfo"]:
        cpi = str(
            ((selected.get("card_args") or {}).get("defaults") or {}).get(
                "cpi"
            )
            or ""
        )
        if f"nodeId_{selected['knowledge_id']}" not in selected_profile["otherInfo"]:
            special.append("otherInfo 的 nodeId 与当前章节不一致")
        if cpi and f"cpi_{cpi}" not in selected_profile["otherInfo"]:
            special.append("otherInfo 的 cpi 与当前班级不一致")
    if selected_profile["duration"] > 1200:
        special.append(
            f"视频时长 {selected_profile['duration']}s（超过 20 分钟）"
        )
    if (
        selected_profile["playTime"] >= selected_profile["duration"]
        and not selected["is_passed"]
    ):
        special.append(
            "播放位置已到结尾但未通过：更像是服务端有效时长/章节任务未满足，"
            "而不是没看完"
        )
    if selected_profile["attDuration"] != selected_profile["duration"]:
        special.append("attDuration 与 duration 不一致")
    if selected_profile["begins"] or selected_profile["ends"]:
        special.append("这是裁剪视频（begins/ends 非 0）")
    if selected_profile["eventArray"]:
        special.append(
            f"存在 eventArray 播放器事件校验（{len(selected_profile['eventArray'])} 项）"
        )
    if selected_profile["supportHeartbeat"] or selected_profile["supportVideoPluginV1"]:
        special.append("启用了播放器心跳/插件校验")
    if selected_profile["isFiled"] == "1" or selected_profile["state"] == "1":
        special.append("isFiled=1 或 state=1，播放器会跳过上报")
    if special:
        print("可能影响完成判定的点：")
        for note in special:
            print(f"  - {note}")


def settle_if_at_end(cookie, course, item, state):
    duration = int(item["VIDEO"]["duration"])
    if item["is_passed"] or item["play_time"] < duration:
        return state, False

    attachment = state.get("attachment") or {}
    video = item["VIDEO"]
    print(
        "已到结尾但服务端未判定通过："
        f"playTime={item['play_time']}s duration={duration}s "
        f"attDuration={attachment.get('attDuration')} "
        f"begins={attachment.get('begins')} ends={attachment.get('ends')}"
    )
    print("服务端把播放位置和有效观看时长分开记录，位置到结尾不等于已通过。")

    print("1) 补发结算心跳...")
    try:
        finish_video(item["VIDEO"], cookie)
    except Exception as exc:
        print(f"结算失败：{exc}")
    try:
        state = refresh_state(cookie, course, item)
    except Exception as exc:
        print(f"刷新视频状态失败：{exc}")
    if item["is_passed"]:
        return state, True
    return state, item["is_passed"]


def find_next_unfinished(videos, current_index):
    for index in range(current_index + 1, len(videos)):
        if not videos[index]["is_passed"]:
            return index
    for index in range(0, current_index):
        if not videos[index]["is_passed"]:
            return index
    return None


def confirm(prompt="继续下一个？(y/N): "):
    return input(prompt).strip().lower() == "y"


def show_item(index, total, item):
    duration = item["VIDEO"]["duration"]
    played = min(item["play_time"], duration)
    status = "已完成" if item["is_passed"] else "未完成"
    label = video_label(item)
    suffix = f"  {label}" if label else ""
    position = position_label(item)
    position_suffix = f"  [{position}]" if position else ""
    print(
        f"\n[{index + 1}/{total}] {item['knowledge_id']}  {item['title']}"
        f"{position_suffix}{suffix}"
        f"  [{status}]  {played}/{duration}s"
    )


def main():
    cookie = input("请输入 Cookie: ").strip()
    if not cookie:
        return

    print("\n正在获取课程列表...")
    try:
        classes = get_class_list(cookie)
    except Exception as exc:
        print(f"获取课程失败：{exc}")
        return
    if not classes:
        print("没有获取到课程，请检查 Cookie")
        return

    print(f"\n共 {len(classes)} 门课程：")
    course = choose(
        classes,
        lambda c: f"{c['course_name']}（{c['name']}）",
    )
    if course is None:
        return

    print(f"\n正在获取《{course['course_name']}》的视频...")
    try:
        videos = get_course_videos(
            cookie,
            course["course_id"],
            course["id"],
            course["cpi"],
        )
    except Exception as exc:
        print(f"获取视频失败：{exc}")
        return
    if not videos:
        print("该课程没有解析到视频")
        return

    print(f"\n共 {len(videos)} 个视频：")
    item = choose(videos, format_progress)
    if item is None:
        return

    index = videos.index(item)
    try:
        state = refresh_state(cookie, course, item)
    except Exception as exc:
        print(f"刷新视频状态失败：{exc}")
        return
    show_item(index, len(videos), item)
    blockers = print_diagnostics(item, state)
    print_comparison(videos, item)
    if blockers and not confirm("检测到可能拦截上报的课程设置，仍要继续？(y/N): "):
        print("已退出")
        return

    max_interval = max(1, int(item["VIDEO"].get("report_interval") or 60))
    default_interval = max_interval
    interval = ask_int(
        f"实时上报间隔秒数（默认 {default_interval}，上限 {max_interval}）: ",
        default_interval,
        1,
    )
    if interval > max_interval:
        print(f"上报间隔不能大于课程设置的 {max_interval}s，已自动调整")
        interval = max_interval
    print("\n逐个确认模式：视频通过后需要按 y 才继续下一个，Ctrl+C 停止。")

    first_pass = True
    while True:
        item = videos[index]
        if first_pass:
            first_pass = False
        else:
            try:
                state = refresh_state(cookie, course, item)
            except Exception as exc:
                print(f"刷新视频状态失败：{exc}")
                return
            show_item(index, len(videos), item)
            print_diagnostics(item, state)

        if not item["is_passed"]:
            before_play_time = item["play_time"]
            duration = int(item["VIDEO"]["duration"])
            if before_play_time >= duration:
                print("服务端记录的播放位置已经在结尾，先补发一次结束事件...")
                state, settled = settle_if_at_end(cookie, course, item, state)
                if settled:
                    show_item(index, len(videos), item)
                else:
                    print(
                        "结束事件仍未通过。真实播放器在此状态会从 0 重新播放，"
                        f"现在按 {interval}s 间隔完整上报，不再从结尾续播..."
                    )
                    try:
                        report_realtime(item["VIDEO"], cookie, 0, interval)
                    except KeyboardInterrupt:
                        print("\n已停止")
                        return
                    except Exception as exc:
                        print(f"上报失败：{exc}")
                        return
                    try:
                        state = refresh_state(cookie, course, item)
                    except Exception as exc:
                        print(f"刷新视频状态失败：{exc}")
                        return
                    show_item(index, len(videos), item)
            else:
                print("开始实时上报...")
                try:
                    report_realtime(
                        item["VIDEO"], cookie, item["play_time"], interval
                    )
                except KeyboardInterrupt:
                    print("\n已停止")
                    return
                except Exception as exc:
                    print(f"上报失败：{exc}")
                    return

                try:
                    state = refresh_state(cookie, course, item)
                except Exception as exc:
                    print(f"刷新视频状态失败：{exc}")
                    return
                show_item(index, len(videos), item)
                state, settled = settle_if_at_end(cookie, course, item, state)
                if settled:
                    show_item(index, len(videos), item)

            if not item["is_passed"]:
                if before_play_time >= int(item["VIDEO"]["duration"]):
                    print(
                        "服务端记录的播放位置已经在结尾，卡住的是有效观看时长；"
                        "结尾重放仍未通过。"
                    )
                elif item["play_time"] <= before_play_time:
                    print(
                        "服务端没有记录任何新进度（play_time 未增加），"
                        "说明心跳请求被拒绝，而不是观看时长不够。"
                    )
                if confirm("仍未通过，是否从 0 重试当前视频？(y/N): "):
                    try:
                        report_realtime(item["VIDEO"], cookie, 0, interval)
                    except KeyboardInterrupt:
                        print("\n已停止")
                        return
                    except Exception as exc:
                        print(f"上报失败：{exc}")
                        return
                    try:
                        state = refresh_state(cookie, course, item)
                    except Exception as exc:
                        print(f"刷新视频状态失败：{exc}")
                        return
                    show_item(index, len(videos), item)
                    state, settled = settle_if_at_end(
                        cookie, course, item, state
                    )
                    if settled:
                        show_item(index, len(videos), item)
                if not item["is_passed"]:
                    print("当前视频仍未通过，退出")
                    return

        next_index = find_next_unfinished(videos, index)
        if next_index is None:
            print("\n全部视频已完成")
            return

        index = next_index
        item = videos[index]
        print(f"\n下一个未完成：[{index + 1}/{len(videos)}] {item['knowledge_id']}  {item['title']}")
        # if not confirm():
        #     print("已退出")
        #     return


if __name__ == "__main__":
    main()
