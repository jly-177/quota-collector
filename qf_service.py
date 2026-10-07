# -*- coding: utf-8 -*-
"""百度千帆（DuMate）自建签到服务 —— 纯标准库，零依赖。

作用：作为 web_server.py 的千帆适配器上游。web_server.py 通过 QF_BASE_URL 指向本服务，
    本服务内部再调用百度千帆官方接口 https://console.bce.baidu.com/api/dumate/* 完成签到/积分/活动任务，
    并把结果包装成 web_server.py 期望的契约（/api/status、/api/history、/api/activity、
    /api/activity/complete-all、/api/activity/draw）。

官方接口（鉴权 = 解密后的百度 Cookie，即 qf_cookie.txt；来自 DuMate 桌面端 auth.json 的 AES-GCM 解密）：
    签到        POST /api/dumate/points/loginBonus                  body {}
    签到信息    GET  /api/dumate/points/loginBonusInfo
    积分总览    GET  /api/dumate/points/quota_overview?timezone=..&clientType=windows&ignoreLoginBonus=true
    任务列表    GET  /api/dumate/activity/growth-plan/tasks
    完成任务    POST /api/dumate/activity/growth-plan/task/complete  body {"task_id": <id>} -> {"reward_count": n}
    抽奖状态    GET  /api/dumate/activity/growth-plan/draw/status
    抽奖        POST /api/dumate/activity/growth-plan/draw
    领奖        POST /api/dumate/activity/growth-plan/prize/claim    body {"draw_record_id": .., "contact": ..}

配置（环境变量优先，其次同目录文件）：
    QF_ACCESS_TOKEN      服务口令：本服务校验 ?token= 用（与 web_server 的 QF_ACCESS_TOKEN 一致）
                         缺省读取 qf_token.txt
    QF_COOKIE            百度 Cookie 请求头字符串（由 _qf_extract_login.py 从桌面端导出）
                         缺省读取 qf_cookie.txt
    QF_DUMATE_DEVICE_ID  设备 X-Dumate-Device-Id（可选，某些接口需要）
                         缺省读取 qf_device.txt
    QF_SERVICE_HOST      监听地址，默认 0.0.0.0
    QF_SERVICE_PORT      监听端口，默认 8786
"""
import json
import os
import sys
import time
import threading
import urllib.request
import urllib.error
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DUMATE_BASE = "https://console.bce.baidu.com"


# ============================ 配置 ============================
def _read_file(name):
    try:
        with open(os.path.join(BASE_DIR, name), "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


SERVICE_TOKEN = os.environ.get("QF_ACCESS_TOKEN", "") or _read_file("qf_token.txt")
DUMATE_COOKIE = os.environ.get("QF_COOKIE", "") or _read_file("qf_cookie.txt")
DUMATE_DEVICE_ID = os.environ.get("QF_DUMATE_DEVICE_ID", "") or _read_file("qf_device.txt")
HOST = os.environ.get("QF_SERVICE_HOST", "0.0.0.0")
PORT = int(os.environ.get("QF_SERVICE_PORT", "8786"))

# 签到记录 / 积分快照持久化
DATA_FILE = os.path.join(BASE_DIR, "qf_service_data.json")
_GROWTH_PLAN = "growth_plan_2026"

_lock = threading.Lock()


# ============================ 持久化 ============================
def _load_data():
    with _lock:
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            d = {}
        d.setdefault("history", [])        # [{date, status, message}]
        d.setdefault("points_snapshot", {})
        return d


def _save_data(d):
    with _lock:
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


# ============================ DuMate 客户端 ============================
def _unpack(obj):
    """BCE 响应可能是 {code:0,result:{..}} / {code:0,data:{..}} / 直接对象，统一取有效体。"""
    if not isinstance(obj, dict):
        return obj
    if "result" in obj and obj["result"] is not None:
        return obj["result"]
    if "data" in obj and isinstance(obj["data"], (dict, list)):
        return obj["data"]
    return obj


def _bce(path, method="GET", body=None, timeout=30):
    """调用百度千帆官方接口，返回解包后的 result（code!=0 或网络错误会抛异常）。"""
    if not DUMATE_COOKIE:
        raise RuntimeError("未配置 QF_COOKIE（百度 Cookie）")
    url = DUMATE_BASE + "/" + path.lstrip("/")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Cookie", DUMATE_COOKIE)
    if DUMATE_DEVICE_ID:
        req.add_header("X-Dumate-Device-Id", DUMATE_DEVICE_ID)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/plain, */*")
    req.add_header("User-Agent",
                   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) DuMate/1.0.82 Chrome/131.0.0.0 Safari/537.36")
    req.add_header("Origin", "https://console.bce.baidu.com")
    req.add_header("Referer", "https://console.bce.baidu.com/")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            obj = json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        t = e.read().decode("utf-8", "replace")
        raise RuntimeError("DuMate http=%s %s" % (e.code, t[:300]))
    except Exception as e:
        raise RuntimeError("DuMate 请求失败: %s" % repr(e))

    if isinstance(obj, dict):
        code = obj.get("code", obj.get("errno", 0))
        if code not in (0, None, "", "0"):
            raise RuntimeError("DuMate code=%s msg=%s" % (
                code, obj.get("message") or obj.get("msg") or obj.get("error") or ""))
    return _unpack(obj)


def _today():
    return time.strftime("%Y-%m-%d", time.localtime())


def _num(v):
    """把 BCE 返回的积分字符串（如 "520.00"）转成数字，失败返回 None。"""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


# ============================ 签到 / 积分 ============================
def _signin_info():
    return _bce("/api/dumate/points/loginBonusInfo", "GET")


def _quota_overview():
    tz = os.environ.get("QF_TIMEZONE", "Asia/Shanghai")
    return _bce("/api/dumate/points/quota_overview?timezone=%s&clientType=windows&ignoreLoginBonus=true" % urllib.parse.quote(tz), "GET")


def _do_signin():
    return _bce("/api/dumate/points/loginBonus", "POST", body={})


def do_signin_safe():
    """尝试签到；返回 (signed_ok:bool, message:str)。幂等，幂等失败不抛。"""
    try:
        if _already_signed_today():
            return "already", "今天已签到"
        res = _do_signin()
        ok = True
        # 某些版本返回 {signed:true} 或 bool
        if isinstance(res, dict):
            ok = bool(res.get("signed", res.get("success", res.get("claimed", True))))
        elif isinstance(res, bool):
            ok = res
        msg = "签到成功" if ok else ("签到结果未知: %s" % (json.dumps(res, ensure_ascii=False)[:120]))
        if ok:
            _append_history(_today(), "success", msg)
        return "success" if ok else "failed", msg
    except Exception as e:
        return "error", str(e)


def _already_signed_today():
    try:
        info = _signin_info()
        days = info.get("signInDays") or info.get("sign_in_days") or []
        return _today() in [str(x)[:10] for x in days]
    except Exception:
        return False


def _append_history(date, status, message):
    d = _load_data()
    d["history"] = [h for h in d["history"] if h.get("date") != date]
    d["history"].insert(0, {"date": date, "status": status, "message": message})
    d["history"] = d["history"][:60]
    _save_data(d)


def _points_snapshot_save(snap):
    d = _load_data()
    d["points_snapshot"] = snap
    d["points_snapshot"]["ts"] = int(time.time())
    _save_data(d)


def get_status():
    """组 /api/status 数据：signin + points。任一上游抖动都会尽量降级。"""
    d = _load_data()
    signin = {"signedToday": False, "totalTimes": 0}
    points = {"totalPoints": None, "usedPoints": None, "available": None}
    points_stale = False

    # 签到状态
    try:
        info = _signin_info()
        days = info.get("signInDays") or info.get("sign_in_days") or []
        signin["signedToday"] = _today() in [str(x)[:10] for x in days]
        signin["totalTimes"] = info.get("totalTimes") or info.get("total_times") or len(days)
    except Exception as e:
        # 读不到签到信息时，用今日历史兜底
        for h in d.get("history", []):
            if h.get("date") == _today():
                signin["signedToday"] = h.get("status") == "success"
                break

    # 积分
    try:
        q = _quota_overview()
        points["totalPoints"] = _num(q.get("totalPoints")) if isinstance(q, dict) else None
        points["usedPoints"] = _num(q.get("usedPoints")) if isinstance(q, dict) else None
        avail = _num(q.get("totalAvailablePoints")) or _num(q.get("availablePoints")) or _num(q.get("available"))
        if avail is None:
            t, u = points["totalPoints"], points["usedPoints"]
            if t is not None and u is not None:
                avail = t - u
        points["available"] = avail
        _points_snapshot_save({k: v for k, v in points.items() if v is not None})
    except Exception:
        snap = d.get("points_snapshot") or {}
        points_stale = True
        points["totalPoints"] = snap.get("totalPoints")
        points["usedPoints"] = snap.get("usedPoints")
        points["available"] = snap.get("available")

    return {"signin": signin, "points": points, "pointsStale": points_stale}


# ============================ 活动中心（growth_plan_2026） ============================
def _task_list():
    return _bce("/api/dumate/activity/growth-plan/tasks", "GET")


def _task_complete(task_id):
    return _bce("/api/dumate/activity/growth-plan/task/complete", "POST", body={"task_id": task_id})


def _draw_status():
    return _bce("/api/dumate/activity/growth-plan/draw/status", "GET")


def _draw():
    return _bce("/api/dumate/activity/growth-plan/draw", "POST", body={})


def _normalize_activity(raw_tasks):
    """把官方活动任务响应规范化成 web_server 契约的 groups/tasks 结构。

    官方 tasks 可能是 [{group_code, group_name, tasks:[...]}] 或已扁平 [{...}]。
    任务字段：task_id/task_type/title/sub_title/completed_count/repeat_count。
    """
    groups = []
    flat = []
    pending = 0
    done = 0

    def _make_task(t, gname, gcode):
        rc = int(t.get("repeat_count") or t.get("repeatCount") or 1) or 1
        cc = int(t.get("completed_count") or t.get("completedCount") or 0)
        completed = cc >= rc
        return {
            "task_id": t.get("task_id") or t.get("taskId"),
            "title": t.get("title") or "",
            "sub_title": t.get("sub_title") or t.get("subTitle") or "",
            "task_type": t.get("task_type") or t.get("taskType") or "",
            "repeat_count": rc,
            "completed_count": cc,
            "done": completed,
        }, (gname or ""), (gcode or "")

    if isinstance(raw_tasks, list):
        for g in raw_tasks:
            if isinstance(g, dict) and isinstance(g.get("tasks"), list):
                gname = g.get("group_name") or g.get("groupName") or ""
                gcode = g.get("group_code") or g.get("groupCode") or ""
                tasks_out = []
                for t in g["tasks"]:
                    nt, _, _ = _make_task(t, gname, gcode)
                    tasks_out.append(nt)
                    flat.append(nt)
                groups.append({"group_code": gcode, "name": gname, "tasks": tasks_out})
            elif isinstance(g, dict):
                nt, gname, gcode = _make_task(g, "", "")
                flat.append(nt)
                groups.append({"group_code": gcode, "name": gname, "tasks": [nt]})

    for nt in flat:
        if nt["done"]:
            done += 1
        else:
            pending += 1
    return groups, flat, pending, done


def get_activity():
    raw = _task_list()
    groups, flat, pending, done = _normalize_activity(
        raw if isinstance(raw, list) else raw.get("groups", raw.get("tasks", raw.get("list", []))))

    draw = {"remaining": None, "error": None}
    try:
        ds = _draw_status()
        if isinstance(ds, dict):
            draw["remaining"] = ds.get("remaining") or ds.get("drawTimes") or ds.get("remaining_draws")
    except Exception as e:
        draw["error"] = str(e)

    return {
        "groups": groups,
        "total": len(flat),
        "done": done,
        "pending": pending,
        "draw": draw,
        "rows": flat,
    }


def complete_all():
    """一键完成所有未完成任务（幂等），轮询直到 pending=0 或不再减少。"""
    unsupported = []
    ok_count = 0
    rounds = 0
    total = 0
    prev_pending = 1 << 30
    for _ in range(10):
        act = get_activity()
        total = act["total"]
        pending = act["pending"]
        if pending == 0:
            break
        if pending >= prev_pending:
            break
        prev_pending = pending
        rounds += 1
        made = False
        for nt in act["rows"]:
            if nt["done"] or not nt["task_id"]:
                continue
            try:
                _task_complete(nt["task_id"])
                ok_count += 1
                made = True
            except Exception as e:
                unsupported.append({"task_id": nt["task_id"], "title": nt["title"], "err": str(e)})
        if not made:
            break
    return {"ok_count": ok_count, "total": total, "rounds": rounds, "unsupported": unsupported}


def do_draw():
    res = _draw()
    act = get_activity()
    return {"result": res, "remaining": act["draw"].get("remaining")}


# ============================ 定时签到 ============================
def _scheduler_loop():
    while True:
        try:
            if not _already_signed_today():
                st, msg = do_signin_safe()
                print("[qf] 定时签到 %s -> %s: %s" % (_today(), st, msg), flush=True)
        except Exception as e:
            print("[qf] 定时签到异常: %s" % e, flush=True)
        time.sleep(30 * 60)


# ============================ HTTP 服务 ============================
class Handler(BaseHTTPRequestHandler):
    server_version = "QFService/1.0"

    def log_message(self, fmt, *args):
        pass

    def _token_ok(self):
        if not SERVICE_TOKEN:
            return True
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        tok = (q.get("token") or [""])[0]
        return tok == SERVICE_TOKEN

    def _send(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._token_ok():
            return self._send({"ok": False, "error": "token 校验失败"}, 401)
        p = urllib.parse.urlparse(self.path).path.lower()
        try:
            if p.endswith("/api/status"):
                return self._send({"ok": True, "data": get_status()})
            if p.endswith("/api/history"):
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                days = int((q.get("days") or ["7"])[0])
                d = _load_data()
                return self._send({"ok": True, "data": d["history"][:days]})
            if p.endswith("/api/activity"):
                return self._send({"ok": True, "data": get_activity()})
            return self._send({"ok": False, "error": "未知接口 %s" % p}, 404)
        except Exception as e:
            return self._send({"ok": False, "error": str(e)}, 500)

    def do_POST(self):
        if not self._token_ok():
            return self._send({"ok": False, "error": "token 校验失败"}, 401)
        p = urllib.parse.urlparse(self.path).path.lower()
        try:
            if p.endswith("/api/activity/complete-all"):
                return self._send({"ok": True, "data": complete_all()})
            if p.endswith("/api/activity/draw"):
                return self._send({"ok": True, "data": do_draw()})
            if p.endswith("/api/signin"):
                st, msg = do_signin_safe()
                return self._send({"ok": st != "error", "data": {"status": st, "message": msg},
                                   "error": None if st != "error" else msg})
            return self._send({"ok": False, "error": "未知接口 %s" % p}, 404)
        except Exception as e:
            return self._send({"ok": False, "error": str(e)}, 500)


def main():
    if not DUMATE_COOKIE:
        print("[qf] 警告：尚未配置 QF_COOKIE（qf_cookie.txt），"
              "接口会报「未配置百度 Cookie」。", flush=True)
    thr = threading.Thread(target=_scheduler_loop, daemon=True)
    thr.start()
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print("[qf] 千帆签到服务已启动 http://%s:%s  (service_token=%s, cookie=%s, device_id=%s)" % (
        HOST, PORT, "已配置" if SERVICE_TOKEN else "未配置",
        "已配置(%d 字节)" % len(DUMATE_COOKIE) if DUMATE_COOKIE else "未配置",
        DUMATE_DEVICE_ID or "未配置"), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()