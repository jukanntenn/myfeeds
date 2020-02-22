import asyncio
import logging
from datetime import datetime
from typing import Dict, Union

import httpx
from bs4 import BeautifulSoup

from myfeeds import env
from myfeeds.config import config
import contextvars

youku_marker = contextvars.ContextVar("youku marker")
weibo_marker = contextvars.ContextVar("weibo marker")
bilibili_marker = contextvars.ContextVar("bilibili marker")

youku_marker.set(None)
weibo_marker.set(None)
bilibili_marker.set(None)


class Feeder:
    default_sources = ["weibo", "bilibili", "youku"]
    source_url = {
        "weibo": "https://m.weibo.cn/profile/info",
        "bilibili": "https://api.bilibili.com/x/space/arc/search",
        "youku": "http://i.youku.com/u/",
    }

    def __init__(self, sources=None):
        self.sources = sources or self.default_sources
        self.logger = logging.getLogger("feeder")

    # 微博
    async def fetch_weibo_statuses(self, uid):
        params = {"uid": uid}
        url = self.source_url["weibo"]
        try:
            response = await self.request(url, params=params)
            return response["data"].get("statuses", [])
        except Exception as e:
            self.logger.exception(e, exc_info=True)

    def parse_weibo_status(self, status):
        created_at = datetime.strptime(status["created_at"], "%a %b %d %H:%M:%S %z %Y")
        timestamp = created_at.timestamp()
        parsed = {
            "source": "weibo",
            "timestamp": timestamp,
            "created_at": created_at,
            "text": status["text"],
            "screen_name": status["user"]["screen_name"],
            "comments_count": status["comments_count"],
            "attitudes_count": status["attitudes_count"],
            "link": "https://m.weibo.cn/detail/" + status["mid"],
        }
        if "retweeted_status" in status:
            retweeted = status["retweeted_status"]
            parsed["retweeted"] = self.parse_weibo_status(retweeted)
        return parsed

    def prepare_weibo_feed(self, statuses):
        if len(statuses) == 0:
            return ""

        statuses = sorted(statuses, key=lambda s: s["timestamp"], reverse=True)
        marker = weibo_marker.get()
        if marker is None:
            statuses = statuses[:1]
        else:
            statuses = [s for s in statuses if s["timestamp"] > marker]
        weibo_marker.set(datetime.now().timestamp())
        return env.get_template("weibo_statuses.md").render(statuses=statuses)

    async def weibo_task(self, uid):
        while True:
            statuses = await self.fetch_weibo_statuses(uid)
            if statuses:
                parsed_statuses = []
                for status in statuses:
                    parsed_statuses.append(self.parse_weibo_status(status))
                feed = self.prepare_weibo_feed(parsed_statuses)
                await self.push(feed, "微博")
            await self.reportable_sleep(10 * 60, name="微博 Feeder")

    # B 站
    async def fetch_bilibili_upunuxi_submissions(self, mid):
        params = {"mid": mid, "ps": 10, "pn": 1}
        url = self.source_url["bilibili"]
        try:
            response: Dict = await self.request(url, params=params)
            return response["data"]["list"]["vlist"]
        except Exception as e:
            self.logger.exception(e, exc_info=True)

    def parse_bilibili_upunuxi_submission(self, submission):
        return {
            "title": submission["title"],
            "timestamp": submission["created"],
            "created_at": datetime.fromtimestamp(submission["created"]),
            "length": submission["length"],
            "author": submission["author"],
            "link": "https://www.bilibili.com/video/av" + str(submission["aid"]),
        }

    def prepare_bilibili_feed(self, submissions):
        if len(submissions) == 0:
            return ""

        submissions = sorted(submissions, key=lambda s: s["timestamp"], reverse=True)
        marker = bilibili_marker.get()
        if marker is None:
            submissions = submissions[:1]
        else:
            submissions = [s for s in submissions if s["timestamp"] > marker]
        bilibili_marker.set(datetime.now().timestamp())
        return env.get_template("bilibili_submissions.md").render(
            submissions=submissions
        )

    async def bilibili_task(self, uid):
        while True:
            submissions = await self.fetch_bilibili_upunuxi_submissions(uid)
            parsed_submissions = []
            for submission in submissions:
                parsed_submissions.append(
                    self.parse_bilibili_upunuxi_submission(submission)
                )
            feed = self.prepare_bilibili_feed(parsed_submissions)
            await self.push(feed, "Bilibili")
            await self.reportable_sleep(10 * 60, name="Bilibili Feeder")

    # 优酷
    async def fetch_youku_videos(self, uid):
        url = self.source_url["youku"] + str(uid)
        try:
            response = await self.request(url)
            soup = BeautifulSoup(response, "html.parser")
            videos = soup.find_all("div", class_="v va")
            return videos[:5]
        except Exception as e:
            self.logger.exception(e, exc_info=True)

    def parse_youku_video(self, video):
        v_meta_link = video.find("div", class_="v-link")
        a = v_meta_link.a
        title = a["title"]
        link = a["href"]
        length = v_meta_link.find("span", class_="v-time").text
        pub_time_des = video.find("span", class_="v-publishtime").text
        return {
            "title": title,
            "link": link,
            "pub_time_des": pub_time_des,
            "length": length,
        }

    def prepare_youku_feed(self, videos):
        if len(videos) == 0:
            return ""

        marker = youku_marker.get()
        if marker is None:
            videos = videos[:1]
        else:
            targets = videos[:]
            videos = []
            for v in targets:
                if v["title"] == marker:
                    break
                videos.append(v)
        if videos:
            youku_marker.set(videos[0]["title"])
        return env.get_template("youku_videos.md").render(videos=videos)

    async def youku_task(self, uid):
        while True:
            videos = await self.fetch_youku_videos(uid)
            parsed_videos = []
            for video in videos:
                parsed_videos.append(self.parse_youku_video(video))
            feed = self.prepare_youku_feed(parsed_videos)
            await self.push(feed, "优酷")
            await self.reportable_sleep(10 * 60, name="优酷 Feeder")

    async def push(self, feed, source):
        if not feed:
            return

        text = f"[{source}]"
        url = f"https://sc.ftqq.com/{config.send_key}.send"
        await self.request(url, "POST", data={"text": text, "desp": feed})
        self.logger.info("Push a %s feed: %s", source, feed)

    # 启动
    async def start(self):
        tasks = []
        for source in self.sources:
            for id_ in config.sources.get(source):
                tasks.append(getattr(self, f"{source}_task")(id_))
        await asyncio.gather(*tasks)

    def run(self):
        asyncio.run(self.start())

    # 辅助方法
    async def request(
        self, url, method="GET", headers=None, params=None, data=None, json=None
    ) -> Union[Dict, str]:
        self.logger.debug(
            "%s %s, request: headers=%s params=%s data=%s json=%s",
            method,
            url,
            headers,
            params,
            data,
            json,
        )
        async with httpx.AsyncClient() as client:
            res = await client.request(
                method,
                url,
                headers=headers,
                params=params,
                data=data,
                json=json,
                timeout=None,
            )
        self.logger.debug(
            "%s %s, response: status_code=%s headers=%s res_text=%s",
            method,
            url,
            res.status_code,
            headers,
            res.text,
        )

        res.raise_for_status()
        res_text = res.text
        if res_text.startswith("{") or res_text.startswith("["):
            return res.json()
        return res_text

    async def reportable_sleep(self, seconds, name=""):
        for i in range(seconds):
            if i % 60 == 0:
                self.logger.info("%s 正在待机, 将在%s分钟后重新启动...", name, (seconds - i) // 60)
            await asyncio.sleep(1)


if __name__ == "__main__":
    feeder = Feeder(sources=[k.lower() for k in config.sources.keys()])
    feeder.run()
