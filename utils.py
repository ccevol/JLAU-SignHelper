# -*- coding: utf-8 -*-
"""
@File                : utils.py
@Github              : https://github.com/Jayve
@Last modified by    : Jayve
@Last modified time  : 2021-6-18 18:38:37
"""
import datetime
import re
import time
from json.decoder import JSONDecodeError

import requests


def resp_parse_json(resp: requests.Response):
    try:
        r = resp.json()
    except JSONDecodeError:
        if 'html' in resp.text:       # 返回网页，抛出标题
            message = re.findall("(?<=<title>).*(?=</title>)", resp.text)[0]
            raise Exception(message)
        elif resp.text:                 # 有返回值，抛出返回值
            raise Exception(resp.text)
        elif resp.status_code != 200:   # 无返回值，且状态码不是200，抛出状态码
            raise Exception(resp.status_code)
        else:                           # 无返回值，且状态码是200，抛出空异常
            raise Exception()
    else:
        return r


def text_mask(text: str, start: int = 0, end: int = -0, mask="*"):
    masked = text.replace(text[start:end], mask * (len(text[start:end])))
    return masked


def get_time():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def get_v_time():
    return int(round(time.time() * 100000))


def get_time_no_second():
    return time.strftime("%Y-%m-%d %H:%M", time.localtime())


def get_7_day_ago():
    now = datetime.datetime.now()
    delta = datetime.timedelta(days=-7)
    n_days = now + delta
    return n_days.strftime('%Y-%m-%d')


def get_today():
    return time.strftime("%Y-%m-%d", time.localtime())


def desc_sort(array, key="FeedbackTime"):
    for i in range(len(array) - 1):
        for j in range(len(array) - 1 - i):
            if array[j][key] < array[j + 1][key]:
                array[j], array[j + 1] = array[j + 1], array[j]
    return array
