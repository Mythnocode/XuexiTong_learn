import requests
def get_class_list(COOKIE):
    getClass_url="https://mooc1-api.chaoxing.com/mycourse/backclazzdata?view=json&rss=1"
    headers={
        "Cookie": COOKIE,
        "user-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/155.0.0.0 Safari/537.36"
    }
    r=requests.get(getClass_url, headers=headers,timeout=20)
    data=r.json()
    if data.get("result") != 1:
        raise RuntimeError(f"获取课程失败: {data.get('msg')}，Cookie 可能已过期")
    class_list=[]
    for ch in data["channelList"]:
        cl = ch["content"]
        course = (cl.get("course") or {}).get("data") or [{}]
        # print(cl["id"], cl["cpi"], cl["name"], course[0].get("id"), course[0].get("name"))
        class_list.append({
            "id": cl["id"],
            "cpi": cl["cpi"],
            "name": cl["name"],
            "course_id": course[0].get("id"),
            "course_name": course[0].get("name"),
        })
    return class_list
def print_class_list(class_list):
    print("课程列表:\n")
    for cl in class_list:
        print(f"{cl['id']} | {cl['cpi']} | {cl['name']} | {cl['course_id']} | {cl['course_name']}")
