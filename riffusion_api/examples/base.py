from riffusion_api import RiffusionAPI

account = RiffusionAPI(sb_api_auth_tokens_0="base64-eyJ...") # provide list or str account token
riffusion_tracks = account.generate(prompt="[Instrumental]", music_style="gitar")

for track in riffusion_tracks:
    print(track.lyrics)
    print(track.result_file_path)