import hashlib
import json
import mimetypes
import os
import random
import shutil
import time
import traceback
import uuid
from json import JSONDecodeError
from typing import List

# from memory_profiler import profile
from pydub import AudioSegment
from requests import Session

from ._errors import RiffusionGenerationError, NoAccounts, RiffusionModerationError
from ._types import RiffusionAccount, RiffusionTrack, RiffusionTransformType, RiffusionModels
from .logs import Logs, Color
from .s_utils import random_string

logger = Logs(warnings=True)

json_account_save = "riffusion_accounts.json"

hash_audio_storage ={}


class RiffusionAPI:
    def __init__(self, sb_api_auth_tokens_0: [list, str] = None, proxies=None):  # , refresh_accounts=True
        self.proxies = proxies
        self.api_email = None
        self._session = Session()

        if not sb_api_auth_tokens_0:
            sb_api_auth_tokens_0 = []
        elif isinstance(sb_api_auth_tokens_0, list):
            sb_api_auth_tokens_0 = sb_api_auth_tokens_0
        elif isinstance(sb_api_auth_tokens_0, str):
            sb_api_auth_tokens_0 = [sb_api_auth_tokens_0]
        else:
            raise TypeError("sb_api_auth_tokens_0 must be str, list or None")

        self.sb_api_auth_tokens_0 = sb_api_auth_tokens_0
        self.new_accounts: List[RiffusionAccount] = self.create_account_database(self.sb_api_auth_tokens_0, proxies=self.proxies)

    #     if refresh_accounts:
    #         threading.Thread(target=self.refresh_accounts).start()
    #
    # def refresh_accounts(self, time_refresh=60 * 60 * 12, start_sleep=1600):  # refresh
    #     logger.logging("not need refresh accounts")

    # @profile
    def create_account_database(self, sb_api_auth_tokens_0: List[str], proxies=None, refresh=False) -> List[RiffusionAccount]:
        try:
            with open(json_account_save, "r", encoding="utf-8") as json_file:
                data = json.load(json_file)
        except (FileNotFoundError, JSONDecodeError):
            data = []

        new_instances = []
        new_accounts = []

        # old accounts
        for i, old_account_data in enumerate(data):
            old_email = old_account_data.get('email')
            try:
                expires_at = old_account_data['expires_at']

                if expires_at - 60 * 60 * 24 * 3 > int(time.time()) and not refresh:  # more than 3 days to expire
                    exist_account = RiffusionAccount.from_dict(old_account_data, proxies=proxies)
                    new_instances.append(old_account_data)
                    new_accounts.append(exist_account)
                    logger.logging("Skip refresh", old_email)
                    continue

                logger.logging(f"Try refresh {old_email} ({i + 1}/{len(data)} account)")

                account = RiffusionAccount.from_dict(old_account_data, proxies=proxies)
                account.refresh()

                if account.login_info.expires_at != expires_at:
                    logger.logging(f"Refreshed account: {account.email}")
                    new_instances.append(account.to_dict())
                    new_accounts.append(account)
                else:
                    logger.logging(f"Cant refresh {old_account_data['email']}! Pass new sb_api_auth_token_0!",
                                   color=Color.RED)
                # time.sleep(5)
            except:
                logger.logging(f"Error in refresh: {old_email}", str(traceback.format_exc()))

        exists_user_ids = [key["id"] for key in new_instances]

        # new accounts
        for i, sb_api_auth_token_0 in enumerate(sb_api_auth_tokens_0):
            try:
                logger.logging(f"Login to ({i + 1}/{len(sb_api_auth_tokens_0)} account)")

                new_account = RiffusionAccount(sb_api_auth_token_0)

                if new_account.login_info.user_id not in exists_user_ids:
                    logger.logging(f"Add new account: {new_account.email}")
                    new_instances.append(new_account.to_dict())
                    new_accounts.append(new_account)
                else:
                    logger.logging("Skip account as exists")
                # time.sleep(5)
            except:
                logger.logging("Error in login new account:", str(traceback.format_exc()))

        # if no accounts total
        if len(new_accounts) == 0:
            raise NoAccounts("No riffusion accounts!")

        logger.logging("saved", len(new_accounts), "accounts", color=Color.PURPLE)

        with open(json_account_save, 'w', encoding='utf-8') as f:
            json.dump(new_instances, f, ensure_ascii=False, indent=4)

        return new_accounts
    # @profile
    def _wait_for_uplaod(self, account, file_id, attempts=30):
        for i in range(attempts):
            url = f"https://wb.riffusion.com/transcribe-audio/{file_id}"

            payload = ""
            headers = {
                "accept": "*/*",
                "accept-language": "ru,en;q=0.9",
                "authorization": f"Bearer {account.auth_token}",
                "cache-control": "no-cache",
                "origin": "https://www.riffusion.com",
                "pragma": "no-cache",
                "priority": "u=1, i",
                "referer": "https://www.riffusion.com/",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 YaBrowser/24.12.0.0 Safari/537.36"
            }

            response = self._session.request("GET", url, data=payload, headers=headers, proxies=self.proxies)
            response.close()

            # print(response.json())

            json_data = response.json()

            status = json_data.get('status')

            if not status:
                raise RiffusionGenerationError(f"No status: {json_data}")

            if status in [None, "pending"]:
                time.sleep(5)
            elif status == "complete":
                return json_data['lyrics']
            else:
                raise RiffusionGenerationError(f"Cant upload file: {response.status_code}, {response.text}")

    @staticmethod
    def _file_hash(filepath, algorithm="sha256", chunk_size=8192):
        """Вычисляет хэш файла с использованием указанного алгоритма."""
        hasher = hashlib.new(algorithm)
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    # @profile
    def _upload_file(self, file_path, account:RiffusionAccount) -> [str, str]:
        audio_hash = self._file_hash(file_path)

        if hash_audio_storage.get(account.login_info.user_id):
            result = hash_audio_storage[account.login_info.user_id].get(audio_hash)
            if result:
                logger.logging(f"Use audio from hash", color=Color.GRAY)
                return result

        url = "https://wb.riffusion.com/v2/upload-audio"

        file_ext = os.path.splitext(file_path)[1][1:]
        mimetype, _ = mimetypes.guess_type(file_path)

        headers = {
            "accept": "*/*",
            "accept-language": "ru,en;q=0.9",
            "authorization": f"Bearer {account.auth_token}",
            "cache-control": "no-cache",
            "origin": "https://www.riffusion.com",
            "pragma": "no-cache",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 YaBrowser/24.12.0.0 Safari/537.36"
        }

        # Формирование данных для отправки
        upload_file_id = str(uuid.uuid4())
        payload = {
            'upload_file_id': upload_file_id,
        }

        # Загружаем файл (предполагается, что это бинарный файл, например, аудиофайл)
        files = {
            'file': (f'{uuid.uuid4()}.{file_ext}', open(file_path, 'rb'), mimetype)  # Замените на путь к файлу
        }

        # Отправляем POST запрос
        response = self._session.post(url, headers=headers, data=payload, files=files, proxies=self.proxies)
        response.close()

        # Закрываем файл после отправки запроса
        files['file'][1].close()

        # Выводим ответ
        # print(response.json(), response.status_code)

        transcription_job_id = response.json().get('transcription_job_id')

        if not transcription_job_id:
            raise RiffusionGenerationError(f"No transcription_job_id: {response.json()}")

        result = upload_file_id, self._wait_for_uplaod(account=account, file_id=transcription_job_id)

        if not hash_audio_storage.get(account.login_info.user_id):
            hash_audio_storage[account.login_info.user_id] = {}
        hash_audio_storage[account.login_info.user_id][audio_hash] = result

        return result

    def _get_valid_account(self) -> RiffusionAccount:  # , force_reload=False, attempts=3, need_balance=1
        # return self.new_accounts[0]
        # if force_reload:
        #     logger.logging("Force register new account")

        for cur_account in self.new_accounts:
            if cur_account.timeout_till < time.time():
                logger.logging(f"Selected: {cur_account.email}")
                return cur_account
            else:
                logger.logging(f"Skip {cur_account.email} - in timeout")

        raise NoAccounts("Cant get_valid_account")
    # @profile
    def _wait_for_generate(self, account, job_id, attempts=60) -> RiffusionTrack:
        for i in range(attempts):
            url = f"https://wb.riffusion.com/generate/status/{job_id}"

            payload = ""
            headers = {
                "accept": "*/*",
                "accept-language": "ru,en;q=0.9",
                "authorization": f"Bearer {account.auth_token}",
                "cache-control": "no-cache",
                "origin": "https://www.riffusion.com",
                "pragma": "no-cache",
                "priority": "u=1, i",
                "referer": "https://www.riffusion.com/",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 YaBrowser/24.12.0.0 Safari/537.36"
            }

            response = self._session.request("GET", url, data=payload, headers=headers, proxies=self.proxies)
            response.close()

            response.raise_for_status()

            # print(response.json())
            json_data = response.json()
            status = json_data['status']
            # print(f"status: {status}, {json_data}"[:40])

            if status in ['queued', 'generating_audio']:
                time.sleep(5)
            elif status in ['flagged']:
                raise RiffusionModerationError(f"Error in moderate: {response.text}")
            elif status == "complete":
                return RiffusionTrack.from_json(json_data)
            else:
                raise RiffusionGenerationError(f"Error in generate: {response.text}")
    # @profile
    def generate(self,
                 output_file:str = None,
                 prompt:str = None,
                 music_style="",
                 input_file=None,
                 lyrics_strength=0.5,
                 music_style_strength=0.5,
                 seed=None,
                 weirdness=0.5,
                 transform=RiffusionTransformType.extend,
                 crop_end_at=None,
                 normalized_lyrics_strength=0.5,
                 normalized_sound_prompt_strength=1.0,
                 inpainting_strength=0.5,
                 verbose=False,
                 normalized_weirdness=0.5,
                 attempts=10
                 ) -> List[RiffusionTrack]:
        """
        Генерирует музыкальный трек на основе заданных параметров.

        Параметры:
        - output_file (str): Путь к файлу, в который будет сохранен сгенерированный трек
        - prompt (str): Текст песни. Если None - создаётся автоматически при наличии input_file
        - music_style (str): Стиль музыки
        - input_file (str): Путь к исходному аудиофайлу, который будет использован
        - lyrics_strength (float): Уровень влияния текста песни на генерируемую музыку. Значение от 0 до 1
        - music_style_strength (float): Уровень влияния выбранного музыкального стиля на результат. Значение от 0 до 1
        - seed (int): Сид
        - weirdness (float): Уровень "креативности". Значение от 0 до 1
        - transform (str): Тип преобразования
        - crop_end_at (int): Время в секундах, на котором будет обрезан входной файл
        - normalized_lyrics_strength (float): Нормализованная сила воздействия текста на музыку
        - normalized_sound_prompt_strength (float): Нормализованная сила воздействия звукового запроса на музыку
        - inpainting_strength (float): не знаю :). Значение от 0 до 1
        - verbose (bool): "многословный", не знаю
        - attempts (int): Количество попыток генерации
        """
        if not prompt and not input_file:
            raise RiffusionGenerationError("Должен быть указан prompt или input_audio!")
        if seed is None:
            seed = random.randint(1, 999999)

        if not output_file:
            if input_file:
                input_file_name = os.path.basename(input_file).split(".")[0][:10]
            else:
                input_file_name = "new"

            lyrics_hash = random_string(length=6, input_str=prompt) # if None, will generate random
            output_file = f"{input_file_name}_seed-{seed}_nlyr-str-{normalized_lyrics_strength}_weir-{str(weirdness)[0]}_verb-{verbose}_nprompt_str-{normalized_sound_prompt_strength}_inpaint-{inpainting_strength}_{lyrics_hash}.mp3"

        if os.path.exists(output_file):
            logger.logging(f"File {os.path.abspath(output_file)} exists. It will be removed")

        if input_file:
            shutil.copy(input_file, output_file)  # чтобы не изменить исходный файл
            input_file = output_file

        for i in range(attempts):
            try:
                account = self._get_valid_account()

                url = "https://wb.riffusion.com/generate/compose"

                if not music_style:
                    music_style = "."
                    music_style_strength = 0

                morph_data = None

                if input_file:
                    audio_upload_id, lyrics_transcribed = self._upload_file(file_path=input_file, account=account)
                    # print("audio_upload_id", audio_upload_id)
                    if not prompt:
                        prompt = lyrics_transcribed

                    audio = AudioSegment.from_file(input_file)
                    audio_len = len(audio) / 1000
                    del audio
                    if transform == RiffusionTransformType.extend:
                        if not crop_end_at:
                            crop_end_at = audio_len

                        crop_end_at = min(crop_end_at, 3 * 60)  # max 3:00 extend

                        morph_data = {
                            "audio_upload_id": audio_upload_id,
                            "transform": transform,
                            "crop_end_at": crop_end_at,
                            "duration": audio_len,
                            "normalized_weirdness": normalized_weirdness,
                            "normalized_lyrics_strength": normalized_lyrics_strength,
                            "normalized_sound_prompt_strength": normalized_sound_prompt_strength
                        }
                    elif transform == RiffusionTransformType.cover:
                        morph_data = {
                            "audio_upload_id": audio_upload_id,
                            "transform": transform,
                            "duration": 0,
                            "normalized_cover_strength": inpainting_strength,
                            "normalized_weirdness": normalized_weirdness,
                            "normalized_lyrics_strength": normalized_lyrics_strength,
                            "normalized_sound_prompt_strength": normalized_sound_prompt_strength
                        }

                payload = {
                    "riff_id": "",
                    "conditions": [
                        {
                            "lyrics": prompt,
                            "strength": lyrics_strength,
                            "condition_start": 0,
                            "condition_end": 1
                        },
                        {
                            "prompt": music_style,
                            "strength": music_style_strength,
                            "condition_start": 0,
                            "condition_end": 1
                        }
                    ],
                    "group_id": str(uuid.uuid4()),
                    "advanced_mode": True,
                    "morph": morph_data,
                    "model_public_name": RiffusionModels.fuzz_08,
                    "stream": False,
                    "audio_format": "aac",
                    "verbose": verbose
                }

                if morph_data:
                    payload['morph'] = morph_data

                headers = {
                    "accept": "*/*",
                    "accept-language": "ru,en;q=0.9",
                    "authorization": f"Bearer {account.auth_token}",
                    "cache-control": "no-cache",
                    "content-type": "application/json",
                    "origin": "https://www.riffusion.com",
                    "pragma": "no-cache",
                    "priority": "u=1, i",
                    "referer": "https://www.riffusion.com/",
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 YaBrowser/24.12.0.0 Safari/537.36"
                }

                # print("payload", payload)

                response = self._session.request("POST", url, json=payload, headers=headers, proxies=self.proxies)

                if response.status_code in [429]:
                    logger.logging("Too many requests. Change account")
                    account.timeout_till = time.time() + 60*20 # 20 minutes timeout
                    continue

                response.close()

                # print(response.text)

                json_data = response.json()
                riffusion_tracks = []
                jobs = json_data.get('jobs')
                job_id = json_data.get('job_id')
                if not jobs:
                    if not job_id:
                        raise RiffusionGenerationError(f"No jobs: {json_data}")
                    else:
                        jobs = [{"id":job_id}]
                # print("jobs", jobs)
                for num_job, job in enumerate(jobs):
                    track = self._wait_for_generate(account=account, job_id=job['id'])
                    file_ext = os.path.splitext(output_file)[1][1:]
                    track.save_audio(file_path=output_file.replace(".mp3",f"{num_job}_.mp3"), output_format=file_ext)
                    track.lyrics = prompt
                    riffusion_tracks.append(track)

                return riffusion_tracks
            except Exception as e:
                logger.logging(f"Error {i+1}/{attempts} while generation: {traceback.format_exc()}")
                if attempts == i+1:
                    raise RiffusionGenerationError(f"После {attempts} попыток не удалось создать песню: {e}")
            finally:
                if os.path.exists(output_file):
                    os.remove(output_file)


if __name__ == '__main__':
    account = RiffusionAPI()
    seed = 1
    normalized_lyrics_strength = 0.5
    weirdness = 1
    verbose = False
    normalized_sound_prompt_strength = 0.5
    crop_end_at = 60
    inpainting_strength = 0.8
    input_file = r"E:\Games\for suno\i want minus.mp3"
    # input_file_name = os.path.basename(input_file).split(".")[0]
    track = account.generate(transform=RiffusionTransformType.cover,
                             crop_end_at=60,
                             prompt="[Instrumental]",
                             music_style="gitar, drums, piano",
                             input_file=input_file,
                             normalized_sound_prompt_strength=normalized_sound_prompt_strength,
                             verbose=verbose,
                             inpainting_strength=inpainting_strength,
                             weirdness=weirdness,
                             normalized_lyrics_strength=normalized_lyrics_strength,
                             seed=seed)

    print(track.lyrics)
    print(track.result_file_path)
    # account.login_google()
    # print(account.login_info.access_token)
    # account.refresh()
