import base64
import io
import json
import time
from typing import List, Optional

from ..logs import Logs, Color

import requests
from pydub import AudioSegment

logger = Logs(warnings=True, name="riffusion_typyes")

json_account_save = "riffusion_accounts.json"

class RiffusionModels:
    fuzz_07 = "FUZZ-0.7"
    fuzz_08 = "FUZZ-0.8"


class RiffusionTransformType:
    extend = "extend"
    cover = "cover"


class Condition:
    def __init__(self, prompt: Optional[str], lyrics: Optional[str], strength: float, condition_start: float,
                 condition_end: float, t_start: float, t_end: float):
        self.prompt = prompt
        self.lyrics = lyrics
        self.strength = strength
        self.condition_start = condition_start
        self.condition_end = condition_end
        self.t_start = t_start
        self.t_end = t_end

    def __repr__(self):
        return f"Condition(prompt={self.prompt}, lyrics={self.lyrics}, strength={self.strength}, condition_start={self.condition_start}, condition_end={self.condition_end}, t_start={self.t_start}, t_end={self.t_end})"


# class LyricsTimestamped:
#     def __init__(self, words: List[dict]):
#         self.words = [Word(**word) for word in words]
#
#
# class Word:
#     def __init__(self, text: str, start: float, end: float, line_index: int, index_range: Optional[List[int]]):
#         self.text = text
#         self.start = start
#         self.end = end
#         self.line_index = line_index
#         self.index_range = index_range
#
#     def __repr__(self):
#         return f"Word(text={self.text}, start={self.start}, end={self.end}, line_index={self.line_index}, index_range={self.index_range})"


class RiffusionTrack:
    def __init__(self, audio: str, audio_variation: str, conditions: List[dict], duration_s: float, id: str,
                 lyrics_timestamped: dict, simple_waveform: List[float], status: str, title: str, result_file_path=None,
                 lyrics=None, image=None, *args, **kwargs):
        self.audio = audio
        self.result_file_path = result_file_path
        self.audio_variation = audio_variation
        self.conditions = [Condition(**condition) for condition in conditions]
        self.duration_s = duration_s
        self.id = id
        self.lyrics_timestamped = lyrics_timestamped
        self.simple_waveform = simple_waveform
        self.status = status
        self.title = title
        self.lyrics = lyrics
        self.image = image

    @classmethod
    def from_json(cls, json_data: dict):
        return cls(**json_data)

    def save_audio(self, file_path: str, output_format="aac"):
        audio_data = base64.b64decode(self.audio)
        audio_stream = io.BytesIO(audio_data)
        audio = AudioSegment.from_file(audio_stream)
        audio.export(file_path, format=output_format)
        self.result_file_path = file_path

    def __repr__(self):
        return f"RiffusionTrack(audio={self.audio}, audio_variation={self.audio_variation}, conditions={self.conditions}, duration_s={self.duration_s}, id={self.id}, lyrics_timestamped={self.lyrics_timestamped}, simple_waveform={self.simple_waveform}, status={self.status}, title={self.title})"


class RiffusionLoginInfo:
    def __init__(self, data: [str, dict]):
        from riffusion_api.s_utils import decode_and_parse_invalid_base64

        if isinstance(data, str):
            json_data = decode_and_parse_invalid_base64(data)
        else:
            json_data = data

        # print("json_data", json_data)

        self.access_token = json_data['access_token']
        self.expires_at = json_data['expires_at']
        self.refresh_token = json_data['refresh_token']
        self.user_id = json_data['user']['id']
        self.email = json_data['user']['email']


class RiffusionAccount:
    # expires in 2035
    base_auth_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhndHB6dWtlem9keHJnbWZobHZ5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzcxODc0MTUsImV4cCI6MjA1Mjc2MzQxNX0.Euec5ChPLivlNRbiaGcyLHu-EP_6qYxcIUxV7tiXVpw"

    def __init__(self, sb_api_auth_token_0: str, proxies=None):
        self.login_info = RiffusionLoginInfo(sb_api_auth_token_0.replace("base64-", ""))
        self.proxies = proxies
        self.timeout_till = 0

    # def login_google(self):
    #     code_challenge = random_string(length=36) + "-" + random_string(length=6)
    #     url = "https://api.riffusion.com/auth/v1/authorize"
    #
    #     querystring = {"provider": "google",
    #                    "redirect_to": "https://www.riffusion.com/auth?refresh=true&redirectUrl=https%3A%2F%2Fwww.riffusion.com",
    #                    "code_challenge": code_challenge, "code_challenge_method": "s256"}
    #
    #     payload = ""
    #     headers = {
    #         "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    #         "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    #         "cache-control": "no-cache",
    #         "pragma": "no-cache",
    #         "priority": "u=0, i",
    #         "referer": "https://www.riffusion.com/",
    #         "sec-fetch-dest": "document",
    #         "sec-fetch-mode": "navigate",
    #         "sec-fetch-site": "same-site",
    #         "sec-fetch-user": "?1",
    #         "upgrade-insecure-requests": "1",
    #         "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
    #     }
    #
    #     response = requests.request("GET", url, data=payload, headers=headers, params=querystring, allow_redirects=False)
    #
    #     print("r1", response.status_code, response.headers)
    #
    #     google_url = response.headers['Location']
    #     print("google_url", google_url)
    #
    #     payload = ""
    #     headers = {
    #         "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    #         "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    #         "cache-control": "no-cache",
    #         "pragma": "no-cache",
    #         "priority": "u=0, i",
    #         "referer": "https://www.riffusion.com/",
    #         "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    #         "x-chrome-id-consistency-request": "version=1,client_id=77185425430.apps.googleusercontent.com,device_id=96d54c0c-f8e6-4b6f-92b5-aa3ac2528fc6,signin_mode=all_accounts,signout_mode=show_confirmation"
    #     }
    #
    #     response = requests.request("GET", google_url, data=payload, headers=headers, allow_redirects=False, cookies=create_cookies_dict(self.google_cookies))
    #
    #     print("r2", response.status_code, response.headers)
    #
    #     callback_url = response.headers['Location']
    #
    #     print("callback_url", callback_url)
    #     exit()
    #
    #     payload = ""
    #     headers = {
    #         # "cookie": "ph_phc_AQw23OVpatMbQV6oPTq1Lf6yJOOM415JjJSn1vtRnFC_posthog=%7B%22distinct_id%22%3A%220194bb9e-a63c-72c5-aa25-b1e047c41a46%22%2C%22%24sesid%22%3A%5B1738314542908%2C%220194bb9e-ac17-77e3-82e1-41845cad324c%22%2C1738314525719%5D%2C%22%24initial_person_info%22%3A%7B%22r%22%3A%22%24direct%22%2C%22u%22%3A%22https%3A%2F%2Fwww.riffusion.com%2F%3Ferror%3Dinvalid_request%26error_code%3Dbad_oauth_state%26error_description%3DOAuth%2Bcallback%2Bwith%2Binvalid%2Bstate%22%7D%7D",
    #         "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    #         "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    #         "cache-control": "no-cache",
    #         "pragma": "no-cache",
    #         "sec-fetch-user": "?1",
    #         "upgrade-insecure-requests": "1",
    #         "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
    #     }
    #
    #     response = requests.request("GET", callback_url, data=payload, headers=headers, params=querystring, allow_redirects=False)
    #
    #     print("r3", response.status_code, response.headers)
    #     print("r3", response.cookies.get_dict())
    #
    #     auth_url = response.headers['Location']
    #
    #     print("auth_url", auth_url)

    @property
    def email(self):
        return self.login_info.email

    @property
    def auth_token(self):
        if self.login_info.expires_at - 60 * 10 < time.time():  # not expired token
            self.refresh()
        return self.login_info.access_token

    def refresh(self):
        url = "https://api.riffusion.com/auth/v1/token"

        querystring = {"grant_type": "refresh_token"}

        payload = {"refresh_token": self.login_info.refresh_token}
        headers = {
            "accept": "*/*",
            "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "apikey": self.base_auth_jwt,
            "authorization": f"Bearer {self.base_auth_jwt}",
            "cache-control": "no-cache",
            "content-type": "application/json;charset=UTF-8",
            "origin": "https://www.riffusion.com",
            "pragma": "no-cache",
            "priority": "u=1, i",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
            "x-client-info": "supabase-ssr/0.5.2",
            "x-supabase-api-version": "2024-01-01"
        }

        response = requests.request("POST", url, json=payload, headers=headers, params=querystring,
                                    proxies=self.proxies)

        if response.status_code != 200:
            from riffusion_api._errors import RiffusionRefreshError

            self.timeout_till = time.time() + 60*60 # 1 hour timeout
            raise RiffusionRefreshError(response.text)
        logger.logging(f"Old refresh: {self.login_info.refresh_token}")
        self.login_info = RiffusionLoginInfo(response.json())
        self.save_to_json()
        logger.logging(f"New refresh: {self.login_info.refresh_token}")

        return self.login_info

    def save_to_json(self):
        try:
            with open(json_account_save, 'r', encoding='utf-8') as f:
                instances = json.load(f)
        except FileNotFoundError:
            instances = []

        found_instance = False
        new_instances = []
        for instance in instances:
            if instance['email'] == self.email:
                found_instance = True
                new_instances.append(self.to_dict())
                continue
            new_instances.append(instance)

        if not found_instance:
            new_instances.append(self.to_dict())

        with open(json_account_save, 'w', encoding='utf-8') as f:
            json.dump(new_instances, f, ensure_ascii=False, indent=4)

    @classmethod
    def from_dict(cls, data, proxies=None):
        login_info = RiffusionLoginInfo({
            "access_token": data.get("auth_token"),
            "expires_at": data.get("expires_at"),
            "refresh_token": data.get("refresh_token"),
            "user": {"id": data.get("id"), "email": data.get("email")}
        })

        obj = cls.__new__(cls)
        obj.proxies = proxies
        obj.login_info = login_info
        obj.timeout_till = 0
        return obj

    def to_dict(self):
        return {
            "auth_token": self.login_info.access_token,
            "expires_at": self.login_info.expires_at,
            "refresh_token": self.login_info.refresh_token,
            "id": self.login_info.user_id,
            "email": self.login_info.email
        }
