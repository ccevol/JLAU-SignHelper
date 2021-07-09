# -*- coding: utf-8 -*-
import json
import logging
import re
import traceback
from datetime import datetime, timedelta, timezone

import requests
import urllib3
import yaml
from urllib3.exceptions import InsecureRequestWarning

import utils
from yiban import YiBan
from excthreading import ExcThread

log = logger = logging

logging.getLogger('chardet.charsetprober').setLevel(logging.INFO)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(threadName)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

# 调试模式
DEV_MODE = False

if DEV_MODE:
    urllib3.disable_warnings(InsecureRequestWarning)
    logging.getLogger().setLevel(logging.DEBUG)


# 读取yml配置
def get_config(yaml_file='config.yml'):
    file = open(yaml_file, 'r', encoding="utf-8")
    file_data = file.read()
    file.close()
    userconfig = yaml.load(file_data, Loader=yaml.FullLoader)
    return dict(userconfig)


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
def get_time():
    utc_dt = datetime.utcnow().replace(tzinfo=timezone.utc)
    bj_dt = utc_dt.astimezone(timezone(timedelta(hours=8)))
    return bj_dt.strftime("%Y-%m-%d %H:%M:%S")


# 检查签到任务列表
def do_check_unsigned_tasks(yiban, user):
    user = user['user']
    tasks = yiban.get_sign_tasks()
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
        if yiban.get_sign_task_state(task['id']) == '未签到':
            return task
    status = '今日全部签到已完成'
    send_result(status, **user)
    return ''


# 获取任务详情
def get_task_detail(yiban, params):
    return yiban.get_sign_task_detail(params['id'])


# 填充表单
def do_fill_form(task, params, user):
    user = user['user']
    form = dict()
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
def do_submit_form(yiban, params, form, user):
    user = user['user']
    res = yiban.do_sign_submit(params['id'], form)
    message = res.text
    if message == 'success':
        status = '成功'
        send_result(status, params, **user)
    elif message == 'Applied today':
        status = '今日已签到'
        send_result(status, params, **user)
    elif "<html>" in message:  # html type
        message = "提交时遇到服务器错误" + re.findall("(?<=<title>).*(?=</title>)", message)[0]
        raise Exception(message)
    else:
        raise Exception(message)


# 签到结果处理
def send_result(status, params=None, **user):
    # 拼接推送消息模板
    taskName = '无'
    if params is not None:
        taskName = params['xmmc']
    fmted_time = get_time()
    # 选择使用备注名 或 登录名
    if 'alias' in user:
        if user['alias'] != '' and user['alias'] is not None:
            alias = user['alias']
        else:
            alias = user['username']
    else:
        alias = user['username']
    # 推送前保护隐私
    if len(alias) >= 11:
        alias_mskd = utils.text_mask(alias, start=3, end=-4)  # 手机号保留前三位和后四位
    else:
        alias_mskd = utils.text_mask(alias, end=-1)  # 姓名保留最后一位
    if re.findall('成功|已完|已签', status):
        title = '易班签到结果通知_成功'
    else:
        title = '易班签到结果通知_失败'
    msg = {
        'start': '',
        'time': fmted_time,
        'taskname': taskName,
        'username': alias_mskd,
        'status': status,
        'end': ''
    }
    msg = MESSAGE_TAMPLATE.format(**msg)
    # 向日志记录本轮结果
    result = ""
    if taskName != "无":  # 是否包含任务标题
        result = taskName
    result = result + f"当前用户 {alias} {status}"
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
        data = {
            'token': sckey,
            'title': title,
            'content': msg,
            # 'topic': ''
        }
        # log.debug(data)
        url = 'https://pushplus.hxtrip.com/send'
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
    if qqnum is not None and (qmsgkey is None or qmsgkey == ''):
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
        url = f'https://qmsg.zendee.cn/send/{qmsgkey}'
        res = requests.post(url, data=data, verify=not DEV_MODE).text
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


# 主要签到流程
def dosign(**user):
    # 实例化一个易班用户
    yiban = YiBan(user['user']['username'], user['user']['password'], debug=DEV_MODE)
    # 1 登录易班
    log.info('步骤(1/6) 正在登录易班..')
    token = yiban.login()
    log.debug(token)
    if len(yiban.name) < 5:  # 当用户名为姓名时，显示
        user['user']['username'] = yiban.name
    # 2 登录学工系统
    log.info('步骤(2/6) 正在登录学工系统..')
    yiban.do_auth_home()
    # 3 开始签到
    log.info('步骤(3/6) 正在检查任务状态..')
    params = do_check_unsigned_tasks(yiban=yiban, user=user)  # 按照用户配置，检查任务列表
    if params == '':  # 无可签任务，跳过
        pass
    else:
        log.info('步骤(4/6) 正在获取任务详情..')
        task = get_task_detail(yiban=yiban, params=params)  # 获取任务要求
        log.info('步骤(5/6) 正在预填充表单..')
        form = do_fill_form(task=task, params=params, user=user)  # 填充表单
        log.info('步骤(6/6) 正在向学校提交签到信息..')
        do_submit_form(yiban=yiban, params=params, form=form, user=user)  # 提交表单


# 主函数 创建多线程任务 && 错误回收和处理
def main():
    ths = []
    err = {}
    for index, user in enumerate(config['users']):
        if 'alias' in user['user']:  # 选择使用备注名 或 登录名
            alias = user['user']['alias']
            if alias == '' or alias is None:
                alias = user['user']['username']
        else:
            alias = user['user']['username']
        th = ExcThread(target=dosign, name=f"{index}-{alias}", kwargs={**user})
        ths.append(th)
        th.start()
    for th in ths:
        try:
            th.join()
        except Exception:
            # 获取当前线程对应的用户配置集
            index = int(th.name.split('-')[0])
            current_user_dict = config['users'][index]['user']
            # 通知用户
            status = f'失败，原因是：{str(th.exc[1])}'
            send_result(status, **current_user_dict)
            # 打印异常追踪
            log.error(traceback.format_exc())
            # 将每个异常的信息添加到列表中
            errname = utils.text_mask(th.name, start=th.name.index('-') + 1, end=-1)  # 姓名部分保留最后一位
            err[errname] = str(th.exc[1])
    if len(err) > 0:
        status = f'检测到有用户发生错误：{str(err)}'
        user = config['users'][0]['user']  # 通知第一用户
        send_result(status=status, params=None, **user)
        raise Exception(f'检测到有用户发生错误：{str(err)}')


# 提供给云函数调用的启动函数
def main_handler(event, context):
    global config
    config = get_config(yaml_file='config.yml')
    try:
        main()
    except Exception as e:
        raise e
    else:
        return 'success'


if __name__ == '__main__':
    print(main_handler({}, {}))
