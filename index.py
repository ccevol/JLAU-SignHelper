# -*- coding: utf-8 -*-
import json
import time
import traceback
from datetime import datetime, timedelta, timezone

import urllib3
import yaml

from yiban import *

logging.getLogger('chardet.charsetprober').setLevel(logging.INFO)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

log = logger = logging

# 调试模式
DEV_MODE = False

if DEV_MODE:
    urllib3.disable_warnings(InsecureRequestWarning)
    logging.getLogger().setLevel(logging.DEBUG)


# 读取yml配置
def getYmlConfig(yaml_file='config.yml'):
    file = open(yaml_file, 'r', encoding="utf-8")
    file_data = file.read()
    file.close()
    config = yaml.load(file_data, Loader=yaml.FullLoader)
    return dict(config)


# 全局配置
config = {}
MESSAGE_TAMPLATE = '''
{start:#^18}
{time}
任务：{taskname}
账号：{username}
状态：{status}
{end:#^18}'''


# 获取当前utc时间，并格式化为北京时间
def getTimeStr():
    utc_dt = datetime.utcnow().replace(tzinfo=timezone.utc)
    bj_dt = utc_dt.astimezone(timezone(timedelta(hours=8)))
    return bj_dt.strftime("%Y-%m-%d %H:%M:%S")


# 获取最新未签到任务
def getUnSignedTasks(yiban, user):
    log.info('正在获取最新未签到任务..')
    user = user['user']
    tasks = yiban.getList()
    # log.debug(tasks)
    if len(tasks['data']) < 1:
        message = '当前没有签到任务'
        raise Exception(message)
    # 任务标题筛选
    tasks_target = []
    for task in tasks['data']:
        for title_look_for in config['taskName']:
            # 将标题符合要求的任务加入列表
            if task['xmmc'] == title_look_for['title']:
                tasks_target.append(task)
    # !当未找到目标任务!
    if not tasks_target:
        # 空列表为False
        message = '所有任务标题均不符合要求'
        raise Exception(message)
    # 检查目标任务状态
    for task in tasks_target:
        if yiban.getTaskState(task['id']) == '未签到':
            return task
    status = '今日全部签到已完成'
    sendResult(status, **user)
    return ''


# 获取任务详情
def getDetailTask(yiban, params):
    log.info('正在获取任务详情..')
    return yiban.getTaskDetail(params['id'])


# 填充表单
def fillForm(task, params, user):
    log.info('正在填充表单..')
    user = user['user']
    form = {}
    form['xmqkb'] = {'id': params['id']}
    applyFields = task['data']['applyFields']
    # log.info(applyFields)
    defaults = config['yiban']['defaults']
    for i in range(0, len(applyFields)):
        try:
            default = defaults[i]['default']
        except IndexError:
            # 可能有隐藏问题允许留空，当任务选项数量与配置文件不一致时，忽略
            continue
        applyField = applyFields[i]
        if default['title'] != applyField['fieldzh'] and applyField['sfyc'] != '是':
            message = '第%d个默认配置项错误，请检查' % (i + 1)
            raise Exception(message)
        # 填空题类型
        if applyField['fieldtype'] == 'string_s':
            form[applyField['fielden']] = default['value']
        # 选择题类型
        elif applyField['fieldtype'] == 'customizeEl':
            for el in str(applyField['el']).split('$'):
                if el == default['value']:
                    form[applyField['fielden']] = default['value']
        # log.info(applyFieldItemValues)
    form['type'] = str.lower(params['type'])
    form['location_longitude'] = user['lon']
    form['location_latitude'] = user['lat']
    form['location_address'] = user['address']
    form = json.dumps(form, ensure_ascii=False)
    log.debug(form)
    return form


# 提交签到任务
def submitForm(yiban, user, form, params):
    log.info('正在提交签到信息..')
    user = user['user']
    res = yiban.submit(params['id'], form)
    message = res.text
    if message == 'success':
        status = '成功'
        sendResult(status, params, **user)
    elif message == 'Applied today':
        status = '今日已签到'
        sendResult(status, params, **user)
    else:
        raise Exception(message)


# 签到结果处理
def sendResult(status, params=None, **user):
    # 拼接推送消息模板
    taskName = '无'
    if params is not None:
        taskName = params['xmmc']
    fmted_time = getTimeStr()
    if len(user['username']) == 11:  # 用户名是手机号？
        username = utils.text_mask(user['username'], start=3, end=-4)
    else:
        username = utils.text_mask(user['username'], end=-1)
    if re.findall('成功|已完|已签', status):
        title = '易班签到结果通知_成功'
    else:
        title = '易班签到结果通知_失败'
    msg = {
        'start': '',
        'time': fmted_time,
        'taskname': taskName,
        'username': username,
        'status': status,
        'end': ''
    }
    msg = MESSAGE_TAMPLATE.format(**msg)
    # 向日志记录本轮结果
    result = ""
    if taskName != "无":  # 是否包含任务标题
        result = taskName
    result = result + f"当前用户 {user['username']} {status}"
    if re.findall('检测到有用户', status):  # 是否为监测消息
        log.error(f"{status}")
    elif re.findall('成功|已完成|已签', status):  # 是否包含错误
        log.info(result)
    else:
        log.error(result)
    # 推送方式抉择
    if user['sckey'] != '' and user['sckey'] is not None:
        push_to_pushplus(title=title, msg=msg, sckey=user['sckey'])  # 选择微信推送
    else:
        msg = f'{title}\n{msg}'
        try:
            qmsgkey = user['qmsgkey']
        except KeyError:
            qmsgkey = None
        push_to_qmsg(msg=msg, qmsgkey=qmsgkey, qqnum=user['qq'])  # 选择QQ推送


# 发送微信通知 基于PushPlus
def push_to_pushplus(title, msg, sckey):
    # log.debug(sckey)
    if sckey != '' and sckey is not None:
        log.info('正在发送微信通知。。。')
        url = 'https://pushplus.hxtrip.com/send'
        data = {
            'token': sckey,
            'title': title,
            'content': msg,
            # 'topic': ''
        }
        # log.debug(data)
        res = requests.post(url, data=data, verify=not DEV_MODE).text
        try:
            r = json.loads(res)
        except json.decoder.JSONDecodeError:
            r = {
                "code": -1,
                "msg": "推送服务返回错误，可能推送服务器在维护",
                "data": "接收返回值失败",
                "count": "null"
            }
        # log.debug(res.rspcode)

        # {"code": 200, "msg": "请求成功", "data": "发送消息成功", "count": "null"}
        if r['code'] == 200:
            log.info('发送微信通知成功!')
        else:
            log.error('发送微信通知失败，原因是：' + r['msg'])


# 发送QQ通知 基于qmsg酱
def push_to_qmsg(msg, qmsgkey=None, qqnum=None):
    if qqnum is not None and qmsgkey is None:
        try:
            qmsgkey = config['users'][0]['user']['qmsgkey']
        except KeyError:
            raise Exception('无法推送!当前用户和第一用户的qmsgkey均为空.')
    # log.debug(sckey)
    if qmsgkey != '' and qmsgkey is not None:
        log.info('正在发送qq通知。。。')
        data = {
            'msg': msg,
        }
        if qqnum is not None:
            data['qq'] = qqnum
        # log.debug(data)
        res = requests.post(f'https://qmsg.zendee.cn/send/{qmsgkey}', data=data, verify=not DEV_MODE).text
        try:
            rescode = json.loads(res)
        except json.decoder.JSONDecodeError:
            rescode = {
                'success': False,
                'reason': 'qmsg酱返回值异常，可能推送服务器又挂了',
                'code': -1
            }
        # log.debug(res.rspcode)
        # {"success": true, "reason": "操作成功", "code": 0, "info": {}}
        if rescode['code'] == 0:
            log.info('发送qq通知成功!')
        else:
            log.error('发送qq通知失败，原因是：' + rescode['reason'])


# 签到流程函数 顺序处理签到步骤并提交
def doSign(**user):
    log.info('{0:=^40}'.format(f"START {user['user']['username']}"))  # ===边框顶===

    yiban = YiBan(user['user']['username'], user['user']['password'], debug=DEV_MODE)

    log.info('正在尝试登录..')
    token = yiban.login()
    log.debug(token)
    if len(yiban.name) < 5:
        user['user']['username'] = yiban.name

    log.info('正在获取学工系统iapp地址..')
    yiban.getHome()

    log.info('正在登录学工系统..')
    yiban.auth()

    params = getUnSignedTasks(yiban=yiban, user=user)
    if params != '':  # 有符合要求的任务可签?
        task = getDetailTask(yiban=yiban, params=params)
        form = fillForm(task=task, params=params, user=user)
        submitForm(yiban=yiban, user=user, form=form, params=params)
    log.info('{0:=^40}'.format(f"END {user['user']['username']}"))  # ===边框底===


# 主函数 循环发送用户信息参数 && 异常处理
def main():
    err = {}
    for user in config['users']:
        try:
            doSign(**user)
        except Exception as e:
            # 通知用户
            status = f'失败，原因是：{str(e)}'
            sendResult(status, **user['user'])
            # 打印异常追踪
            log.error(traceback.format_exc())
            # 补全日志块
            log.info('{0:=^40}'.format(f"END {user['user']['username']}"))  # 遇到异常时会中断签到函数，可在此处补全边框底
            # 加入错误集
            if len(user['user']['username']) > 5:  # 用户名大于5个字符？
                username = utils.text_mask(user['user']['username'], start=3, end=-4)
            else:
                username = utils.text_mask(user['user']['username'], end=-1)
            err[username] = str(e)
            continue
        finally:
            time.sleep(2.3)
    if len(err) > 0:
        status = f'检测到有用户发生错误：{str(err)}'
        user = config['users'][0]['user']
        sendResult(status=status, params=None, **user)
        raise Exception("检测到有用户发生错误,请检查日志.")


# 提供给腾讯云函数调用的启动函数
def main_handler(event, context):
    global config
    config = getYmlConfig(yaml_file='config.yml')
    try:
        main()
    except Exception as e:
        raise e
    else:
        return 'success'


if __name__ == '__main__':
    print(main_handler({}, {}))
