import logging
import re
import uuid
from json import JSONDecodeError
from urllib.parse import urlparse, unquote

import requests
import urllib3
from bs4 import BeautifulSoup
from requests import HTTPError
from urllib3.exceptions import InsecureRequestWarning

import utils

log = logger = logging


def get_html_status_text(html: str):
    """
    cdn节点检测到问题时，返回html，本函数解析并返回其错误详情
    :param html: HTML内容
    :return: status_text: 错误详情内容
    """
    bs = BeautifulSoup(html, 'html.parser')
    status_text = bs.find("span", id="status_text").get_text()
    return status_text


class YiBan:
    HEADERS = {
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://xsgl.jlau.edu.cn",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; VOG-AL00 Build/HUAWEIVOG-AL00) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/88.0.4324.181 Mobile Safari/537.36 yiban_android",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": "https://xsgl.jlau.edu.cn/webApp/xuegong/index.html",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,en-US;q=0.8",
        "appversion": "4.9.6",
        "X-Requested-With": "com.yiban.app"
    }

    def __init__(self, account, passwd, debug=False):
        self.account = account
        self.passwd = passwd
        self.access_token = ''
        self.session = requests.session()
        self.name = ''
        self.iapp = ''
        self.debug = debug
        if self.debug:
            urllib3.disable_warnings(InsecureRequestWarning)

    def request(self, url, method="get", data=None, params=None, json=None, cookies=None, max_retry: int = 2, **kwargs):
        for i in range(max_retry + 1):
            try:
                s = self.session
                response = s.request(method, url, params=params, data=data, json=json, headers=self.HEADERS,
                                     cookies=cookies, verify=not self.debug, **kwargs)
            except HTTPError as e:
                log.error(f'HTTP错误:\n{e}')
                log.error(f'第 {i + 1} 次请求失败, 重试...')
            except KeyError as e:
                log.error(f'错误返回值:\n{e}')
                log.error(f'第 {i + 1} 次请求失败, 重试...')
            except Exception as e:
                log.error(f'未知异常:\n{e}')
                log.error(f'第 {i + 1} 次请求失败, 重试...')
            else:
                return response
        raise Exception(f'已重试 {max_retry + 1} 次，HTTP请求全部失败, 放弃.')

    def login(self):
        data = {
            "mobile": self.account,
            "imei": 0,
            "password": self.passwd
        }
        # 调用v3接口登录，无需加密密码
        res = self.request(url="https://mobile.yiban.cn/api/v3/passport/login", method='post', data=data)
        try:
            r = res.json()
        except JSONDecodeError:  # 返回数据非json，尝试分析为html
            status_text = get_html_status_text(res.text)
            raise Exception(f"登录请求发生错误 {res.status_code}，返回：{status_text}")
        except Exception as e:
            raise Exception(f"登录请求发生错误 {type(e)} {str(e)}")

        # {'response': 100, 'message': '请求成功', 'data': {****}}
        # {'response': 101, 'message': '服务忙，请稍后再试。', 'data': []}
        if r is not None and r["response"] == 100:
            self.access_token = r["data"]["user"]["access_token"]
            self.name = r["data"]["user"]["nick"]
            return r
        else:
            raise Exception(f'请求登录发生错误：{r["message"]}')

    def getHome(self):
        params = {
            "access_token": self.access_token,
        }
        res = self.request(url="https://mobile.yiban.cn/api/v3/home", params=params)
        try:
            r = res.json()
        except JSONDecodeError:  # 返回数据非json，尝试分析为html
            status_text = get_html_status_text(res.text)
            raise Exception(f"请求iapp列表发生错误 {res.status_code}，返回：{status_text}")
        except Exception as e:
            raise Exception(f"请求iapp列表发生错误 {type(e)} {str(e)}")

        # {'response': 100, 'message': '请求成功', 'data': {****}}
        # {'response': 101, 'message': '服务忙，请稍后再试。', 'data': []}
        if r is not None and r["response"] == 100:
            # 获取iapp号
            for app in r["data"]["hotApps"]:
                if app["name"] == "吉农学工系统":
                    self.iapp = re.findall(r"(iapp.*)\?", app["url"])[0].split("/")[0]
            return r
        else:
            raise Exception(f'请求iapp列表发生错误：{r["message"]}')

    def auth(self):
        params = {
            "act": self.iapp,
            "v": self.access_token
        }
        # 获取waf_cookie
        v_time = utils.get_v_time()
        self.request(f"http://f.yiban.cn/{self.iapp}/i/{self.access_token}?v_time={v_time}", allow_redirects=False)
        # 尝试检测APP权限
        location = self.request("http://f.yiban.cn/iapp/index", params=params, allow_redirects=False).headers.get(
            "Location")
        # location = https://xsgl.jlau.edu.cn/nonlogin/yiban/authentication/4a46818571558ef9017155f721f20012.htm?verify_request=&yb_uid=
        if location is None:
            raise Exception("该用户可能没进行校方认证，无此APP权限")

        # 登录学工系统
        location_authQYY = self.request(location, allow_redirects=False).headers.get("Location")
        # location_authQYY有两种情况 取决于iapp是否已授权
        # 已授权返回Location https://xsgl.jlau.edu.cn/yiban/authorize.html
        # 未授权返回Location https://openapi.yiban.cn/oauth/authorize

        if "oauth/authorize" in location_authQYY:  # 首次进入iapp，需要点击授权
            data = {'scope': '1,2,3,4,'}
            query_params = urlparse(location_authQYY).query.split('&')
            # log.debug(query_params)
            for line in query_params:
                title, value = line.split("=")
                data[title] = value
            data['redirect_uri'] = unquote(data['redirect_uri'], 'utf-8')
            data['display'] = 'html'
            # 发送确认授权请求
            usersure_res = self.request('https://oauth.yiban.cn/code/usersure', method='post', data=data)
            try:
                usersure_r = usersure_res.json()
            except JSONDecodeError:  # 返回数据非json，尝试分析为html
                status_text = get_html_status_text(usersure_res.text)
                raise Exception(f"授权iapp发生错误 {usersure_res.status_code}，返回：{status_text}")
            except Exception as e:
                raise Exception(f"授权iapp发生错误 {type(e)} {str(e)}")

            # {"code":"s200","reUrl":"https:\/\/f.yiban.cn\/iapp619789\/v\/0e4200ff23de1faa22a2cd6e07615767"}
            if usersure_r['code'] != 's200':
                fail_reason = usersure_r['msgCN']
                raise Exception(f'授权iapp失败！原因是：{fail_reason}')
            # 授权成功，访问其返回的url
            self.request(usersure_r['reUrl'])
        # 最后请求登录本校系统
        compressedCode = location_authQYY.split('?')[1].split('=')[1]
        if compressedCode is None:
            raise Exception('登录学工系统失败！compressedCode为空！')
        params = {
            'compressedCode': compressedCode,
            'deviceId': uuid.uuid1()
        }
        res = self.request(url='https://xsgl.jlau.edu.cn/nonlogin/yiban/authQYY.htm', params=params,
                           allow_redirects=False)
        if res.headers.get('Location') == 'https://xsgl.jlau.edu.cn/webApp/xuegong/index.html#/action/baseIndex/':
            return True
        else:
            return False

    def getList(self):
        data = {
            'pageIndex': 0,
            'pageSize': 10,
            'type': 'yqsjcj'
        }
        try:
            res = self.request("https://xsgl.jlau.edu.cn/syt/zzapply/queryxmqks.htm", method='post', data=data)
            res = res.json()
        except Exception as e:
            raise Exception(f"请求任务列表发生错误 {type(e)} {str(e)}")
        return res

    def getTaskState(self, xmid):
        data = {
            "xmid": xmid,
            "pdnf": 2020
        }
        res = self.request("https://xsgl.jlau.edu.cn/syt/zzapply/checkrestrict.htm", method='post', data=data)
        if res.text == '':
            return '未签到'
        return res.text

    def getTaskDetail(self, xmid):
        data = {
            'projectId': xmid
        }
        try:
            res = self.request("https://xsgl.jlau.edu.cn/syt/zzapi/getBaseApplyInfo.htm", method='post', data=data)
            res = res.json()
        except Exception as e:
            raise Exception(f"请求任务详情发生错误 {type(e)} {str(e)}")
        return res

    def submit(self, xmid, data):
        data = {
            "data": data,
            "msgUrl": f"syt/zzapply/list.htm?type=yqsjcj&xmid={xmid}",
            "multiSelectData": {},
            "uploadFileStr": {}
        }
        return self.request("https://xsgl.jlau.edu.cn/syt/zzapply/operation.htm", method='post', data=data)
