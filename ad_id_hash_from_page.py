# Parse ads pages for images and save hashes to file.
# Use that file to update ads images.

import requests
import os
import json
import re
import config

# Settings
skip_caught = False  # False True
final_file = "ads_final.json"
login_direct = config.login_direct
token_direct = config.token_direct
camp_ids_filter = [710351183, 713391023]  # [] for all.
ad_states = ["OFF", "ON", "SUSPENDED", "OFF_BY_MONITORING"]
cut_url_postfixes = []  # ["&sort", r"\?sort"]
prod_page_pattern = "data-hover-gallery>"
page_text_from = '<meta property="og:image" content="'
page_texts_to = ['">', r"\?u=", '"/>']
host = config.host
im_hash_default = None  # '4hfo3NLFAA50lpvXy3MTSg'
just_non_image_ads = False
just_im_hash_default_ads = False
exclude_ads_ids_file = None  # None 'exclude_ads_ids.csv'
filter_ads_ids_file = None  # None 'filter_ads_ids.csv'
do_not_set_default = True
ad_type = "TextAd"
Use_Operator_Units = "false"  # "true" for an agency accounts.
headers_200 = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.9; rv:45.0) Gecko/20100101 Firefox/45.0"
}
redirect_pattern = None  # r"https://redirect\.|http://redirect\."

if just_non_image_ads and just_im_hash_default_ads:
    raise ValueError("Cannot be both just_non_image_ads and just_im_hash_default_ads")

from utils import Helper, YaDirectHelper

common_instance = Helper()
dir_path = os.path.dirname(os.path.realpath(__file__))
ya_dir_instance = YaDirectHelper(token_direct, login_direct, Use_Operator_Units)

ads = ya_dir_instance.get_ads(
    None,
    None,
    camp_ids_filter,
    ad_states,
    None,
    ["Id"],
    ["Href", "AdImageHash"],
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    None,
)

exclude_ads_ids = set()
ads_to_remove = list()

if skip_caught:
    with open(os.path.join(dir_path, final_file), encoding="utf-8") as ouf:
        d = json.load(ouf)
    for ad in d:
        exclude_ads_ids.add(int(ad["Id"]))

if exclude_ads_ids_file:
    with open(os.path.join(dir_path, exclude_ads_ids_file), encoding="utf-8") as ouf:
        for line in ouf:
            exclude_ads_ids.add(int(line.strip()))

if exclude_ads_ids:
    for ad in ads:
        if int(ad["Id"]) in exclude_ads_ids:
            ads_to_remove.append(ad)

filter_ads_ids = set()
if filter_ads_ids_file:
    with open(os.path.join(dir_path, filter_ads_ids_file), encoding="utf-8") as ouf:
        for line in ouf:
            filter_ads_ids.add(int(line.strip()))

    for ad in ads:
        if int(ad["Id"]) not in filter_ads_ids:
            ads_to_remove.append(ad)

for ad in ads_to_remove:
    ads.remove(ad)

account_urls = set()
ad_id_url = dict()

for ad in ads:
    if ad_type not in ad:
        continue

    if just_non_image_ads and ad["TextAd"]["AdImageHash"]:
        continue

    if just_im_hash_default_ads and ad["TextAd"]["AdImageHash"] != im_hash_default:
        continue

    url = ad["TextAd"]["Href"]

    # Redirect url case.
    if redirect_pattern and re.match(redirect_pattern, url):
        url = re.sub(redirect_pattern, "https://www.", url)

    for cut_url_postfix in cut_url_postfixes:
        url = re.split(cut_url_postfix, url)[0]

    ad_id_url[ad["Id"]] = url
    account_urls.add(url)

url_image_hash = dict()
ad_id_hash = dict()
counter = 0
for url in account_urls:
    counter += 1
    # Get image url.
    url_respond = requests.get(url, headers=headers_200)

    url_respond.encoding = "utf-8"
    page_text = url_respond.text

    (
        is_pattern,
        status_code,
        is_ConnectionError,
        is_TooManyRedirects,
        _,
    ) = common_instance.check_status_text_of_page(url, headers_200, None)

    if (
        not is_pattern
        or status_code != 200
        or is_ConnectionError
        or is_TooManyRedirects
    ):
        image_url = ""
    else:
        prod_url = re.split(prod_page_pattern, page_text)

        # Handle error.
        if len(prod_url) > 1:
            prod_url = prod_url[1]  # [1] [2]

            prod_url = re.split('"', prod_url)[0]
            prod_url = f"{host}{prod_url}"

            # Get image url.
            prod_url_respond = requests.get(prod_url, headers=headers_200)
            prod_url_respond.encoding = "utf-8"
            page_text = prod_url_respond.text

            image_url = re.split(page_text_from, page_text)
            image_url = image_url[1]
            for page_text_to in page_texts_to:
                image_url = re.split(page_text_to, image_url)[0]

        else:
            print(f"No prod_page_pattern at the {url}")
            image_url = ""

    # Get image hash.
    if not image_url:
        if do_not_set_default:
            continue
        im_hash = im_hash_default
    else:
        img_name = re.split("/", image_url)[-1]
        img_name = re.split(r"\?", img_name)[0]  # Make different for convenience.

        common_instance.download_file(image_url, dir_path, img_name, headers_200)

        if "logo" in img_name:
            pass

        common_instance.make_image_square(os.path.join(dir_path, img_name))
        im_hash = common_instance.get_hashes(
            dir_path, img_name, "", login_direct, token_direct
        )

    url_image_hash[url] = im_hash

    if counter % 50 == 0 or counter == len(account_urls):
        for ad_id in ad_id_url:
            if ad_id_url[ad_id] in url_image_hash:
                ad_id_hash[ad_id] = url_image_hash[ad_id_url[ad_id]]

        ads_final = []
        for ad_id in ad_id_hash:
            if just_im_hash_default_ads and ad_id_hash[ad_id] == im_hash_default:
                continue
            dic = {"Id": ad_id, "TextAd": {"AdImageHash": ad_id_hash[ad_id]}}
            ads_final.append(dic)

        ads_final_json = json.dumps(ads_final, indent=4, ensure_ascii=False)
        with open(os.path.join(dir_path, final_file), "w", encoding="utf-8") as ouf:
            ouf.write(ads_final_json)

        with open(
            os.path.join(dir_path, "to_see_step.txt"), "w", encoding="utf-8"
        ) as ouf:
            ouf.write(f"{counter} of {len(account_urls)}, url: {url}")

pass