import os
import json
import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

DEBUG = False

if DEBUG:
    urllib3.disable_warnings(InsecureRequestWarning)


def generate():
    lon = float(input("请输入经度lon的值："))
    lat = float(input("请输入纬度lat的值："))
    params = {
        "key": "3f2d05f6b67340db78bcb1b620dad5f5",
        # "s": "rsv3",
        "language": "zh_cn",
        "location": f"{lon},{lat}",
        # "callback": "jsonp_913764_",
        # "platform": "JS",
        # "logversion": "2.0",
        # "appname": "https://xsgl.jlau.edu.cn/webApp/xuegong/index.html#/action/baseIndex/",
        # "csid": "3214504E-AECF-4C23-A282-255BFE5C7B03",
        "sdkversion": "1.4.15",
        "extensions": "all"
    }
    url = "https://restapi.amap.com/v3/geocode/regeo"
    re = requests.get(url=url, params=params, verify=not DEBUG)
    try:
        res = re.json()
    except json.decoder.JSONDecodeError:
        raise Exception(f"返回值错误：{re.text}")
    try:
        province = res["regeocode"]["addressComponent"]["province"]
        city = res["regeocode"]["addressComponent"]["city"]
        district = res["regeocode"]["addressComponent"]["district"]
        streetNumber_street = res["regeocode"]["addressComponent"]["streetNumber"]["street"]
        streetNumber_number = res["regeocode"]["addressComponent"]["streetNumber"]["number"]
        neighborhood = res["regeocode"]["aois"][0]["name"]
    except KeyError:
        print(f"获取地址内容不正常！\n{res}")
        generate()
    # 吉林省 长春市 南关区 新城大街 2888号 靠近吉林农业大学
    addr = f'{province} {city} {district} {streetNumber_street} {streetNumber_number} 靠近{neighborhood}'
    input(f"生成的地址字段为：\n{addr}\n")
    generate()


if __name__ == '__main__':
    generate()
