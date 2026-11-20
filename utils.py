import os
import sys
import re
import json
import numpy as np
from time import sleep
import requests
import base64
from skimage.io import imread, imsave
from PIL import Image


from constants import YA_DIR_API_IMAGES_URL, YA_DIR_API_ADS_URL


class Helper:
    def check_status_text_of_page(
        self, url, headers_200, awaiting_delivery_checking_text
    ):
        # Returns is pattern in page text, status_code, is_ConnectionError, is_TooManyRedirects error.
        dl_pettern1 = r"globalThis.dataLayer = "
        dl_pettern2 = r"</script>"

        is_ConnectionError = False
        is_awaiting_delivery_text = False

        try:
            url_respond = requests.get(url, headers=headers_200)
        except requests.exceptions.TooManyRedirects:
            return None, None, None, True, is_awaiting_delivery_text
        except requests.exceptions.ConnectionError:
            is_ConnectionError = True
            for i in range(5):
                print("ConnectionError. sleep(12)")
                sleep(12)
                try:
                    url_respond = requests.get(url, headers=headers_200)
                except requests.exceptions.ConnectionError:
                    continue
                is_ConnectionError = False
                break

        if is_ConnectionError:
            print(f"is_ConnectionError {url}")
            return None, None, True, False, is_awaiting_delivery_text

        if url_respond.status_code != 200:
            # Give 2 the second chances.
            sleep(3)
            url_respond = requests.get(url, headers=headers_200)
            if url_respond.status_code != 200:
                sleep(3)
                url_respond = requests.get(url, headers=headers_200)
                if url_respond.status_code != 200:
                    return (
                        None,
                        url_respond.status_code,
                        False,
                        False,
                        is_awaiting_delivery_text,
                    )

        # Check for text existing on the page.
        url_respond.encoding = "utf-8"
        page_text = url_respond.text
        if awaiting_delivery_checking_text:
            is_awaiting_delivery_text = bool(
                re.search(awaiting_delivery_checking_text, page_text)
            )

        # Check for goods.
        data_layer = re.split(dl_pettern1, page_text)

        if len(data_layer) < 2:
            print(f"Bad url because of len(data_layer)<2: {url}\n")
            return (
                False,
                url_respond.status_code,
                False,
                False,
                is_awaiting_delivery_text,
            )

        data_layer = data_layer[1]
        data_layer = re.split(dl_pettern2, data_layer)[0].strip()
        data_layer = json.loads(data_layer)

        if len(data_layer) == 0 or data_layer[0].get("productsQuantityTotal") == "0":
            return (
                False,
                url_respond.status_code,
                False,
                False,
                is_awaiting_delivery_text,
            )

        return True, url_respond.status_code, False, False, is_awaiting_delivery_text

    def download_file(self, url, path_vm, file_name, headers):
        # Download file by chunks to save RAM.
        with requests.get(url, headers=headers, stream=True) as r:
            r.raise_for_status()
            with open(os.path.join(path_vm, file_name), "wb") as f:
                for chunk in r.iter_content(chunk_size=4096):
                    if chunk:
                        f.write(chunk)

    def make_image_square(self, image):
        # Function to square image to prevent distortion of image later.
        # Read image.
        img = imread(image)
        # Get size of image.
        size_img = img.shape

        # ------------------------------------------
        # If item image is black and white then convert it to RGB
        # to prevent concatenation process error and correct pixels measuring.
        if len(size_img) < 3:
            black_white_img = Image.open(image).convert("RGB")
            black_white_img.save(image)
            # Read renewed image again.
            img = imread(image)
            # Get size of image.
            size_img = img.shape
        # ------------------------------------------

        # Count difference between width and height of image.
        diff_width_height = size_img[1] - size_img[0]
        # Stop the function if image is already squared.
        if diff_width_height == 0:
            return "pass"

        # Create white square space.
        img_white = np.zeros([5000, 5000, 3], dtype=np.uint8)
        img_white.fill(255)

        if diff_width_height > 0:  # Use the bigger side.
            img_white_square = img_white[0 : size_img[1], 0 : size_img[1]]
        else:
            img_white_square = img_white[0 : size_img[0], 0 : size_img[0]]

        # Add image to the square.
        # Count half of diff_width_height.
        half = abs(int(diff_width_height / 2))
        if diff_width_height < 0:
            img_white_square[0 : size_img[0], half : half + size_img[1]] = img
        else:
            img_white_square[half : half + size_img[0], 0 : size_img[1]] = img
        # Save new image.
        imsave(image, img_white_square)

    def get_hashes(
        self, path_vm_itself, image_name, default_image_hash, login_direct, token_direct
    ):
        headers = {
            "Authorization": f"Bearer {token_direct}",
            "Client-Login": login_direct,
            "Accept-Language": "en",
        }

        image = open(os.path.join(path_vm_itself, image_name), "rb").read()
        imageData = base64.b64encode(image).decode("utf-8")
        # Upload REGULAR image to Yandex.Direct account.
        body = {
            "method": "add",
            "params": {"AdImages": [{"ImageData": imageData, "Name": image_name}]},
        }
        jsonBody = json.dumps(body, ensure_ascii=False).encode("utf8")
        result = requests.post(YA_DIR_API_IMAGES_URL, jsonBody, headers=headers)
        result = result.json()

        os.remove(os.path.join(path_vm_itself, image_name))

        # Handle errors.
        if "result" in result:
            if "AdImageHash" in result["result"]["AddResults"][0]:
                return result["result"]["AddResults"][0]["AdImageHash"]

        return default_image_hash

    def divide_to_small_groups(self, variety_name, group_size):
        # Divide variety to small groups.
        # Handle case when length of variety_name not bigger than group_size.
        if len(variety_name) > group_size:
            groups_amount = len(variety_name) // group_size
            residue = len(variety_name) % group_size
            divided_groups = []  # To store grouped elements.
            for group_number in range(groups_amount):
                divided_groups.append(
                    variety_name[
                        group_number * group_size : (group_number + 1) * group_size
                    ]
                )
            # Add residue elements.
            if residue > 0:
                divided_groups.append(
                    variety_name[
                        (group_number + 1)
                        * group_size : (group_number + 1)
                        * group_size
                        + residue
                        + 1
                    ]
                )
        # Return the variety if it already not bigger than group_size.
        else:
            divided_groups = [list(variety_name)]
        return divided_groups


common_instance = Helper()


class YaDirectHelper:
    def __init__(self, token_direct, login_direct, Use_Operator_Units):
        self.headers = {
            "Authorization": f"Bearer {token_direct}",
            "Client-Login": login_direct,
            "Accept-Language": "ru",
            "Use-Operator-Units": Use_Operator_Units,  # To use the agency API scores.
        }
        self.token_direct = token_direct
        self.login_direct = login_direct

        # To correct string processing in UTF-8 both Python 2 and Python 3.
        if sys.version_info < (3,):
            def u(x):
                try:
                    return x.encode("utf8")
                except UnicodeDecodeError:
                    return x
        else:
            def u(x):
                if type(x) == type(b""):
                    return x.decode("utf8")
                else:
                    return x

    def get_ads(
        self,
        Ids,
        AdGroupIds,
        CampaignIds,
        States,
        Statuses,
        FieldNames,
        TextAdFieldNames,
        DynamicTextAdFieldNames,
        TextImageAdFieldNames,
        MobileAppAdFieldNames,
        MobileAppImageAdFieldNames,
        TextAdPriceExtensionFieldNames,
        CpmBannerAdBuilderAdFieldNames,
        CpmVideoAdBuilderAdFieldNames,
        SmartAdBuilderAdFieldNames,
        TextAdBuilderAdFieldNames,
        CpcVideoAdBuilderAdFieldNames,
    ):
        if (
            (Ids and AdGroupIds)
            or (Ids and CampaignIds)
            or (AdGroupIds and CampaignIds)
        ):
            raise Exception("Cannot be more than 1 selection criteria")

        ads = []
        if Ids:
            selection_level = "Ids"
            all_selectors = Ids
            group_size = 10000
        elif AdGroupIds:
            selection_level = "AdGroupIds"
            all_selectors = AdGroupIds
            group_size = 1000
        elif CampaignIds:
            selection_level = "CampaignIds"
            all_selectors = CampaignIds
            group_size = 10
        else:
            raise Exception("No selection level set.")

        # Iterate by partitions to avoid too many selection elements error.
        selection_groups = common_instance.divide_to_small_groups(
            all_selectors, group_size
        )

        for elements in selection_groups:
            offset = 0  # Number of objects to get next iteration.
            while True:
                body = {
                    "method": "get",
                    "params": {
                        "SelectionCriteria": {selection_level: elements},
                        "FieldNames": FieldNames,
                        "Page": {"Offset": offset},
                    },
                }

                if TextAdFieldNames:
                    body["params"]["TextAdFieldNames"] = TextAdFieldNames
                if DynamicTextAdFieldNames:
                    body["params"]["DynamicTextAdFieldNames"] = DynamicTextAdFieldNames
                if TextImageAdFieldNames:
                    body["params"]["TextImageAdFieldNames"] = TextImageAdFieldNames
                if MobileAppAdFieldNames:
                    body["params"]["MobileAppAdFieldNames"] = MobileAppAdFieldNames
                if MobileAppImageAdFieldNames:
                    body["params"][
                        "MobileAppImageAdFieldNames"
                    ] = MobileAppImageAdFieldNames
                if TextAdPriceExtensionFieldNames:
                    body["params"][
                        "TextAdPriceExtensionFieldNames"
                    ] = TextAdPriceExtensionFieldNames
                if CpmBannerAdBuilderAdFieldNames:
                    body["params"][
                        "CpmBannerAdBuilderAdFieldNames"
                    ] = CpmBannerAdBuilderAdFieldNames
                if CpmVideoAdBuilderAdFieldNames:
                    body["params"][
                        "CpmVideoAdBuilderAdFieldNames"
                    ] = CpmVideoAdBuilderAdFieldNames
                if SmartAdBuilderAdFieldNames:
                    body["params"][
                        "SmartAdBuilderAdFieldNames"
                    ] = SmartAdBuilderAdFieldNames
                if TextAdBuilderAdFieldNames:
                    body["params"][
                        "TextAdBuilderAdFieldNames"
                    ] = TextAdBuilderAdFieldNames
                if CpcVideoAdBuilderAdFieldNames:
                    body["params"][
                        "CpcVideoAdBuilderAdFieldNames"
                    ] = CpcVideoAdBuilderAdFieldNames

                if States:
                    body["params"]["SelectionCriteria"]["States"] = States
                if Statuses:
                    body["params"]["SelectionCriteria"]["Statuses"] = Statuses

                # Кодирование тела запроса в JSON
                jsonBody = json.dumps(body, ensure_ascii=False).encode("utf8")
                result = requests.post(
                    YA_DIR_API_ADS_URL, jsonBody, headers=self.headers
                )
                result = result.json()
                # To prevent the error.
                if "result" in result:
                    if "Ads" in result["result"]:
                        for ad in result["result"]["Ads"]:
                            ads.append(ad)

                # Check whether all objects were got or not.
                if "LimitedBy" not in result["result"]:
                    break
                else:
                    offset = result["result"]["LimitedBy"]

        return ads

    def update_ads(self, ads_data_update):
        result_to_see = ""
        counter = 0
        body = {"method": "update", "params": {"Ads": []}}
        for ad_data in ads_data_update:
            counter += 1
            body["params"]["Ads"].append(ad_data)

            if counter % 1000 == 0:
                jsonBody = json.dumps(body, ensure_ascii=False).encode("utf8")
                result = requests.post(
                    YA_DIR_API_ADS_URL, jsonBody, headers=self.headers
                )
                result_to_see += f"{result.json()}\n\n"
                body["params"]["Ads"] = []

        if counter % 1000 != 0:
            jsonBody = json.dumps(body, ensure_ascii=False).encode("utf8")
            result = requests.post(YA_DIR_API_ADS_URL, jsonBody, headers=self.headers)
            result_to_see += f"{result.json()}\n\n"

        return result_to_see