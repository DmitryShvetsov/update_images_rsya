import os
import json
import config


# Settings
file_update_data = os.path.join(os.path.dirname(os.path.realpath(__file__)), "ads_final.json")
token_direct = config.token_direct
login_direct = config.login_direct

from utils import YaDirectHelper

with open(file_update_data, encoding="utf-8") as json_data:
    ads_data_update = json.load(json_data)

ya_dir_instance = YaDirectHelper(token_direct, login_direct, "false")
result_to_see = ya_dir_instance.update_ads(ads_data_update)

pass