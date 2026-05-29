# coding=utf-8
#!/usr/bin/env python3

import json
import requests


class Spider:
    def getName(self):
        return "咖啡直播"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.host = "https://kafeizhibo.com"
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/134.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://kafeizhibo.com/live/all",
        }

    def log(self, msg):
        print("[咖啡直播] " + str(msg))

    def _normalize_url(self, path):
        if not path:
            return ""
        if path.startswith("http"):
            return path
        if path.startswith("//"):
            return "https:" + path
        return self.host + ("" if path.startswith("/") else "/") + path

    def _get(self, path, params=None, referer=None):
        headers = dict(self.headers)
        if referer:
            headers["Referer"] = referer
        resp = requests.get(self.host + path, headers=headers, params=params, timeout=10)
        return resp.json()

    def _fetch_live_all(self):
        return self._get("/api/v1/archor", referer=self.host + "/live/all")

    def _parse_live_list(self, items, category_filter=None):
        seen_rooms = set()
        result = []
        for item in items:
            if category_filter is not None and str(item.get("category")) != str(category_filter):
                continue

            room_id = str(item.get("room_id", ""))
            if not room_id or room_id in seen_rooms:
                continue
            seen_rooms.add(room_id)

            home = item.get("home_team", "")
            away = item.get("away_team", "")
            league = item.get("league_name", "")
            h_score = item.get("home_score", 0)
            a_score = item.get("away_score", 0)
            title = "{} vs {} ({})".format(home, away, league)

            pic = self._normalize_url(item.get("screenshot", ""))
            if not pic or "default" in pic:
                match_info = item.get("match_info") or {}
                pic = self._normalize_url(match_info.get("home_team_logo", ""))

            result.append(
                {
                    "vod_id": "live_{}".format(room_id),
                    "vod_name": "直播 " + title,
                    "vod_pic": pic,
                    "vod_remarks": "{} - {} | {}".format(
                        h_score, a_score, item.get("name", "")
                    ),
                }
            )
        return result

    def _detail_live(self, room_id):
        try:
            data = self._get(
                "/api/v1/room/{}".format(room_id),
                referer=self.host + "/room/{}".format(room_id),
            )
            if data.get("code") != 200 or not data.get("data"):
                return {"list": []}

            detail = data["data"]
            room_info = detail.get("room_info", {})
            signals = detail.get("signals", [])

            home = room_info.get("home_team", "")
            away = room_info.get("away_team", "")
            league = room_info.get("league", "")
            h_score = room_info.get("home_score", 0)
            a_score = room_info.get("away_score", 0)
            title = "{} vs {} ({})".format(home, away, league)

            teams = detail.get("teams", {})
            pic = self._normalize_url((teams.get("home") or {}).get("logo", ""))

            episodes = []
            for signal in signals:
                url = signal.get("stream_url", "")
                if not url:
                    continue
                name = signal.get("name", "线路")
                episodes.append("{}${}".format(name, url))

            if not episodes:
                archor = detail.get("archor", {})
                url = archor.get("stream_url", "")
                if url:
                    episodes.append("{}${}".format(archor.get("name", "直播"), url))

            vod = {
                "vod_id": "live_{}".format(room_id),
                "vod_name": "直播 " + title,
                "vod_pic": pic,
                "vod_content": "{} {} vs {}，比分 {} - {}".format(
                    league, home, away, h_score, a_score
                ),
                "vod_play_from": "直播线路",
                "vod_play_url": "#".join(episodes),
            }
            return {"list": [vod]}
        except Exception as err:
            self.log("直播详情失败: " + str(err))
            return {"list": []}

    def _fetch_recordings(self, page=1, size=30, league=None, type_id=None):
        params = {"page": page, "size": size}
        if league:
            params["league"] = league
        elif type_id and type_id not in ("all", "nba", "live_all", "live_1", "live_2"):
            params["type"] = type_id

        headers = dict(self.headers)
        headers["Referer"] = self.host + "/pc/replay"
        resp = requests.get(
            self.host + "/api/v1/recordings",
            headers=headers,
            params=params,
            timeout=10,
        )
        return resp.json()

    def _parse_video_list(self, items):
        result = []
        for item in items:
            title = "{} vs {} ({})".format(
                item.get("home_team", ""),
                item.get("away_team", ""),
                item.get("league_name", ""),
            )
            score = "{} - {}".format(item.get("home_score", 0), item.get("away_score", 0))
            pic = item.get("cover_image", "")
            if pic and not pic.startswith("http"):
                pic = self._normalize_url(pic)
            if not pic or "default_cover" in pic:
                pic = self._normalize_url(item.get("home_team_logo", ""))

            remarks = "{} | {} | {}个录像".format(
                score,
                item.get("start_time", ""),
                item.get("recording_count", 0),
            )
            result.append(
                {
                    "vod_id": str(item.get("match_id", "")),
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remarks,
                }
            )
        return result

    def _detail_recording(self, vid):
        try:
            headers = dict(self.headers)
            headers["Referer"] = self.host + "/pc/replay"
            resp = requests.get(
                "{}/api/v1/match/{}/recordings".format(self.host, vid),
                headers=headers,
                timeout=10,
            )
            data = resp.json()
            if data.get("code") != 200 or not data.get("data"):
                return {"list": []}

            match = data["data"]["match"]
            replays = data["data"].get("replays", [])
            highlights = data["data"].get("highlights", [])

            title = "{} vs {} ({})".format(
                match.get("home_team", ""),
                match.get("away_team", ""),
                match.get("league_name", ""),
            )
            pic = self._normalize_url(
                match.get("home_team_logo") or match.get("away_team_logo") or ""
            )

            episodes = []
            for idx, replay in enumerate(replays):
                video_url = replay.get("video_url")
                if video_url:
                    name = replay.get("title") or "录像{}".format(idx + 1)
                    episodes.append("{}${}".format(name, video_url))

            for idx, replay in enumerate(highlights):
                video_url = replay.get("video_url")
                if video_url:
                    name = replay.get("title") or "集锦{}".format(idx + 1)
                    episodes.append("{}${}".format(name, video_url))

            vod = {
                "vod_id": str(vid),
                "vod_name": title,
                "vod_pic": pic,
                "vod_content": "{} {} {} vs {}，比分 {} - {}，比赛时间：{}".format(
                    match.get("league_name", ""),
                    match.get("match_round", ""),
                    match.get("home_team", ""),
                    match.get("away_team", ""),
                    match.get("home_score", 0),
                    match.get("away_score", 0),
                    match.get("start_time", ""),
                ),
                "vod_play_from": "录像源",
                "vod_play_url": "#".join(episodes),
            }
            return {"list": [vod]}
        except Exception as err:
            self.log("录像详情失败: " + str(err))
            return {"list": []}

    def homeContent(self, filter):
        categories = [
            {"type_id": "live_all", "type_name": "直播全部"},
            {"type_id": "live_1", "type_name": "直播足球"},
            {"type_id": "live_2", "type_name": "直播篮球"},
            {"type_id": "all", "type_name": "录像全部"},
            {"type_id": "1", "type_name": "录像足球"},
            {"type_id": "2", "type_name": "录像篮球"},
            {"type_id": "nba", "type_name": "录像NBA"},
        ]
        try:
            data = self._fetch_live_all()
            vod_list = (
                self._parse_live_list(data.get("data", []))
                if data.get("code") == 200
                else []
            )
        except Exception as err:
            self.log("首页加载失败: " + str(err))
            vod_list = []
        return {"class": categories, "list": vod_list}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1

        if tid in ("live_all", "live_1", "live_2"):
            try:
                data = self._fetch_live_all()
                if data.get("code") == 200:
                    category = None if tid == "live_all" else tid.split("_")[1]
                    vod_list = self._parse_live_list(
                        data.get("data", []), category_filter=category
                    )
                else:
                    vod_list = []
            except Exception as err:
                self.log("直播分类失败: " + str(err))
                vod_list = []
            return {
                "list": vod_list,
                "page": 1,
                "pagecount": 1,
                "limit": 100,
                "total": len(vod_list),
            }

        try:
            if tid == "nba":
                data = self._fetch_recordings(page, 20, league="NBA")
                size = 20
            elif tid == "all":
                data = self._fetch_recordings(page, 30)
                size = 30
            else:
                data = self._fetch_recordings(page, 30, type_id=tid)
                size = 30

            vod_list = []
            pagecount = 1
            if data.get("code") == 200 and data.get("data"):
                vod_list = self._parse_video_list(data["data"])
                pagecount = page + 1 if len(data["data"]) == size else page
        except Exception as err:
            self.log("录像分类失败: " + str(err))
            vod_list = []
            pagecount = 1

        return {
            "list": vod_list,
            "page": page,
            "pagecount": pagecount,
            "limit": 30,
            "total": len(vod_list),
        }

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) and ids else str(ids)
        if vid.startswith("live_"):
            return self._detail_live(vid[5:])
        return self._detail_recording(vid)

    def searchContent(self, key, quick, pg=1):
        if not key:
            return {"list": []}

        keyword = key.lower()
        result = []

        try:
            data = self._fetch_live_all()
            if data.get("code") == 200:
                for item in data.get("data", []):
                    if (
                        keyword in item.get("home_team", "").lower()
                        or keyword in item.get("away_team", "").lower()
                        or keyword in item.get("league_name", "").lower()
                        or keyword in item.get("title", "").lower()
                    ):
                        room_id = str(item.get("room_id", ""))
                        home = item.get("home_team", "")
                        away = item.get("away_team", "")
                        league = item.get("league_name", "")
                        result.append(
                            {
                                "vod_id": "live_{}".format(room_id),
                                "vod_name": "直播 {} vs {} ({})".format(
                                    home, away, league
                                ),
                                "vod_pic": "",
                                "vod_remarks": "直播中",
                            }
                        )
        except Exception as err:
            self.log("搜索直播失败: " + str(err))

        try:
            data = self._fetch_recordings(1, 100)
            if data.get("code") == 200:
                for item in data.get("data", []):
                    if (
                        keyword in item.get("home_team", "").lower()
                        or keyword in item.get("away_team", "").lower()
                        or keyword in item.get("league_name", "").lower()
                    ):
                        title = "{} vs {} ({})".format(
                            item.get("home_team", ""),
                            item.get("away_team", ""),
                            item.get("league_name", ""),
                        )
                        result.append(
                            {
                                "vod_id": str(item.get("match_id", "")),
                                "vod_name": title,
                                "vod_pic": "",
                                "vod_remarks": "{} - {}".format(
                                    item.get("home_score", 0),
                                    item.get("away_score", 0),
                                ),
                            }
                        )
        except Exception as err:
            self.log("搜索录像失败: " + str(err))

        return {"list": result, "page": 1, "pagecount": 1}

    def playerContent(self, flag, id, vipFlags):
        return {
            "parse": 0,
            "playUrl": "",
            "url": id,
            "header": json.dumps(
                {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.host,
                    "Origin": self.host,
                }
            ),
        }
