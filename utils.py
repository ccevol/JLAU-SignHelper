import datetime
import time


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
