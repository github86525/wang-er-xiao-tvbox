# coding=utf-8
#!/usr/bin/env python3

import json
import re
from datetime import datetime, timedelta

import requests


class Spider:
    def getName(self):
        return "857体育"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.host = "https://857zbw2.com"
        self.static_api = "https://json.yyzb456.top"
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/134.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Referer": self.host + "/match.html",
            "Origin": self.host,
        }

    def log(self, msg):
        print("[857体育] " + str(msg))

    def _china_now(self):
        return datetime.utcnow() + timedelta(hours=8)

    def _date_key(self, offset=0):
        return (self._china_now() + timedelta(days=offset)).strftime("%Y%m%d")

    def _date_label(self, offset):
        dt = self._china_now() + timedelta(days=offset)
        if offset == 0:
            return "今日赛程"
        if offset == 1:
            return "明日赛程"
        if offset == 2:
            return "后天赛程"
        return dt.strftime("%m-%d赛程")

    def _normalize_url(self, url):
        if not url:
            return ""
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return "https:" + url
        return self.host + ("" if url.startswith("/") else "/") + url

    def _jsonp_to_json(self, text):
        text = (text or "").strip()
        if not text:
            return {}
        match = re.search(r"^[^(]+\((.*)\)\s*$", text, re.S)
        if not match:
            return {}
        try:
            return json.loads(match.group(1))
        except Exception as err:
            self.log("JSONP解析失败: " + str(err))
            return {}

    def _get_jsonp(self, path, referer=None):
        headers = dict(self.headers)
        if referer:
            headers["Referer"] = referer
        resp = requests.get(
            self.static_api + path,
            headers=headers,
            timeout=10,
        )
        resp.encoding = "utf-8"
        return self._jsonp_to_json(resp.text)

    def _get_match_list(self, date_key):
        return self._get_jsonp(
            "/match/matches_{}.json?v={}".format(date_key, int(self._china_now().timestamp())),
            referer=self.host + "/match.html",
        )

    def _get_all_live_rooms(self):
        return self._get_jsonp(
            "/all_live_rooms.json?v={}".format(int(self._china_now().timestamp())),
            referer=self.host + "/match.html",
        )

    def _get_room_detail(self, room_num, schedule_id=""):
        headers = dict(self.headers)
        headers["Referer"] = self.host + "/room/{}?scheduleId={}".format(room_num, schedule_id)
        resp = requests.get(
            self.static_api + "/room/{}/detail.json?v={}".format(
                room_num, int(self._china_now().timestamp())
            ),
            headers=headers,
            timeout=10,
        )
        resp.encoding = "utf-8"
        return self._jsonp_to_json(resp.text)

    def _flatten_live_rooms(self, payload):
        data = payload.get("data") or {}
        result = []
        seen = set()
        for _, items in data.items():
            for item in items or []:
                room_num = str(item.get("roomNum", ""))
                if not room_num or room_num in seen:
                    continue
                seen.add(room_num)
                result.append(item)
        result.sort(key=lambda x: x.get("viewCount", 0), reverse=True)
        return result

    def _parse_live_rooms(self, items):
        result = []
        for item in items:
            room_num = str(item.get("roomNum", ""))
            anchor = item.get("anchor") or {}
            result.append(
                {
                    "vod_id": "room|{}".format(room_num),
                    "vod_name": item.get("title", "") or anchor.get("nickName", room_num),
                    "vod_pic": self._normalize_url(
                        item.get("cutOutCustomCoverUrl")
                        or item.get("customCoverUrl")
                        or anchor.get("cutOutIcon")
                        or anchor.get("icon")
                    ),
                    "vod_remarks": "在线 {} | {}".format(
                        item.get("viewCount", 0),
                        anchor.get("nickName", ""),
                    ),
                }
            )
        return result

    def _parse_match_list(self, items, category_filter=None):
        result = []
        for item in items:
            if category_filter and item.get("categoryName") != category_filter:
                continue

            schedule_id = str(item.get("scheduleId", ""))
            if not schedule_id:
                continue

            title = "{} VS {}".format(item.get("hostName", ""), item.get("guestName", ""))
            league = item.get("subCateName") or item.get("categoryName") or ""
            pic = self._normalize_url(item.get("hostIcon") or item.get("categoryIcon") or "")
            remarks = "{} | {}-{} | {}".format(
                item.get("matchStatusDesc", "未开"),
                item.get("hostScore", 0),
                item.get("guestScore", 0),
                league,
            )
            result.append(
                {
                    "vod_id": "match|{}|{}".format(
                        item.get("_date_key", self._date_key(0)), schedule_id
                    ),
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remarks,
                }
            )
        return result

    def _find_match(self, date_key, schedule_id):
        data = self._get_match_list(date_key)
        if data.get("code") != 200:
            return None
        for item in data.get("data") or []:
            if str(item.get("scheduleId", "")) == str(schedule_id):
                item["_date_key"] = date_key
                return item
        return None

    def homeContent(self, filter):
        classes = [{"type_id": "live_rooms", "type_name": "直播中"}]
        for offset in range(7):
            date_key = self._date_key(offset)
            classes.append(
                {
                    "type_id": "date_{}".format(date_key),
                    "type_name": self._date_label(offset),
                }
            )

        try:
            live_payload = self._get_all_live_rooms()
            rooms = self._flatten_live_rooms(live_payload)[:20]
            vod_list = self._parse_live_rooms(rooms)
        except Exception as err:
            self.log("首页加载失败: " + str(err))
            vod_list = []

        return {"class": classes, "list": vod_list}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1

        if tid == "live_rooms":
            try:
                live_payload = self._get_all_live_rooms()
                vod_list = self._parse_live_rooms(self._flatten_live_rooms(live_payload))
            except Exception as err:
                self.log("直播列表失败: " + str(err))
                vod_list = []
            return {
                "list": vod_list,
                "page": 1,
                "pagecount": 1,
                "limit": 200,
                "total": len(vod_list),
            }

        if tid.startswith("date_"):
            date_key = tid.split("_", 1)[1]
            try:
                payload = self._get_match_list(date_key)
                items = payload.get("data") or []
                for item in items:
                    item["_date_key"] = date_key
                vod_list = self._parse_match_list(items)
            except Exception as err:
                self.log("赛程列表失败: " + str(err))
                vod_list = []
            return {
                "list": vod_list,
                "page": page,
                "pagecount": page,
                "limit": 200,
                "total": len(vod_list),
            }

        return {"list": [], "page": 1, "pagecount": 1, "limit": 0, "total": 0}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) and ids else str(ids)

        if vid.startswith("room|"):
            room_num = vid.split("|", 1)[1]
            try:
                detail = self._get_room_detail(room_num)
                room = (detail.get("data") or {}).get("room") or {}
                anchor = room.get("anchor") or {}
                vod = {
                    "vod_id": vid,
                    "vod_name": room.get("title", "") or anchor.get("nickName", room_num),
                    "vod_pic": self._normalize_url(
                        room.get("cutOutCustomCoverUrl")
                        or room.get("customCoverUrl")
                        or anchor.get("cutOutIcon")
                        or anchor.get("icon")
                    ),
                    "vod_content": room.get("detail", "") or room.get("notice", ""),
                    "vod_play_from": "857直播",
                    "vod_play_url": "#".join(
                        [
                            "高清$stream|{}|hd".format(room_num),
                            "标清$stream|{}|sd".format(room_num),
                        ]
                    ),
                }
                return {"list": [vod]}
            except Exception as err:
                self.log("房间详情失败: " + str(err))
                return {"list": []}

        if vid.startswith("match|"):
            parts = vid.split("|")
            if len(parts) < 3:
                return {"list": []}

            date_key = parts[1]
            schedule_id = parts[2]
            try:
                match = self._find_match(date_key, schedule_id)
                if not match:
                    return {"list": []}

                episodes = []
                for anchor in match.get("anchors") or []:
                    room_num = str(((anchor.get("anchor") or {}).get("roomNum")) or "")
                    if not room_num:
                        continue
                    episodes.append(
                        "{}${}".format(
                            anchor.get("nickName", room_num),
                            "stream|{}|hd|{}".format(room_num, schedule_id),
                        )
                    )

                vod = {
                    "vod_id": vid,
                    "vod_name": "{} VS {}".format(
                        match.get("hostName", ""),
                        match.get("guestName", ""),
                    ),
                    "vod_pic": self._normalize_url(
                        match.get("hostIcon") or match.get("categoryIcon") or ""
                    ),
                    "vod_content": "{} | {} | 比分 {}-{}".format(
                        match.get("subCateName") or match.get("categoryName") or "",
                        match.get("matchStatusDesc", "未开"),
                        match.get("hostScore", 0),
                        match.get("guestScore", 0),
                    ),
                    "vod_play_from": "主播线路",
                    "vod_play_url": "#".join(episodes),
                }
                return {"list": [vod]}
            except Exception as err:
                self.log("赛程详情失败: " + str(err))
                return {"list": []}

        return {"list": []}

    def searchContent(self, key, quick, pg=1):
        if not key:
            return {"list": []}

        keyword = key.lower()
        result = []

        try:
            live_payload = self._get_all_live_rooms()
            for item in self._flatten_live_rooms(live_payload):
                anchor = item.get("anchor") or {}
                text = " ".join(
                    [
                        str(item.get("title", "")),
                        str(anchor.get("nickName", "")),
                        str(item.get("detail", "")),
                    ]
                ).lower()
                if keyword in text:
                    result.extend(self._parse_live_rooms([item]))
        except Exception as err:
            self.log("搜索直播失败: " + str(err))

        try:
            for offset in range(7):
                date_key = self._date_key(offset)
                payload = self._get_match_list(date_key)
                for item in payload.get("data") or []:
                    item["_date_key"] = date_key
                    hay = " ".join(
                        [
                            str(item.get("hostName", "")),
                            str(item.get("guestName", "")),
                            str(item.get("subCateName", "")),
                            str(item.get("categoryName", "")),
                        ]
                    ).lower()
                    if keyword in hay:
                        result.extend(self._parse_match_list([item]))
        except Exception as err:
            self.log("搜索赛程失败: " + str(err))

        return {"list": result, "page": 1, "pagecount": 1}

    def playerContent(self, flag, id, vipFlags):
        parts = str(id).split("|")
        if len(parts) < 3:
            return {"parse": 0, "playUrl": "", "url": id}

        mode = parts[0]
        room_num = parts[1]
        quality = parts[2]
        schedule_id = parts[3] if len(parts) > 3 else ""

        try:
            detail = self._get_room_detail(room_num, schedule_id)
            stream = (detail.get("data") or {}).get("stream") or {}

            if quality == "hd":
                url = stream.get("hdM3u8") or stream.get("hdFlv") or stream.get("m3u8") or stream.get("flv")
            else:
                url = stream.get("m3u8") or stream.get("flv") or stream.get("hdM3u8") or stream.get("hdFlv")

            return {
                "parse": 0,
                "playUrl": "",
                "url": url or "",
                "header": json.dumps(
                    {
                        "User-Agent": self.headers["User-Agent"],
                        "Referer": self.host + "/room/{}?scheduleId={}".format(room_num, schedule_id),
                        "Origin": self.host,
                    }
                ),
            }
        except Exception as err:
            self.log("播放地址获取失败: " + str(err))
            return {"parse": 0, "playUrl": "", "url": ""}
