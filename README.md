<div align="center"> 
    <h1>JLAU-SignHelper</h1>
    <p>自动提交每日签到任务</p>
</div>

[![GitHub stars](https://img.shields.io/github/stars/Jayve/JLAU-SignHelper?style=flat-square)](https://github.com/Jayve/JLAU-SignHelper/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/Jayve/JLAU-SignHelper?style=flat-square)](https://github.com/Jayve/JLAU-SignHelper/network)
[![GitHub issues](https://img.shields.io/github/issues/Jayve/JLAU-SignHelper?style=flat-square)](https://github.com/Jayve/JLAU-SignHelper/issues)

## 功能特点

- [x] **支持多用户多线程异步签到**
- [x] **支持模拟多机型随机UA**
- [x] **支持微信 & QQ 推送签到通知 (基于PushPlus、QMsg)**
- [x] **详细的异常处理与反馈**
- [ ] **干净高效的代码**
- [ ] **好评如潮的客户服务**

## 使用方法
### A.部署到服务器/本机直接运行

- 安装`Python3`

- 在根目录执行以下命令，下载安装必需的`python第三方包`

  ```
  pip install -t . -r requirements.txt
  ```

- 重命名文件`config_example.yml `-> `config.yml`

- 修改配置文件`config.yml`，按照注释文本提示，填写必要用户配置

  完成以上步骤，在根目录执行以下命令，运行签到

  ```
  python index.py
  ```

### B.部署到云函数Serverless

首先下载源码到本机，进行必要的步骤：

- 本机安装`Python3`

- 在根目录执行以下命令，下载安装必需的`python第三方包`

  ```
  pip install -t . -r requirements.txt
  ```

- 重命名`config_example.yml`为`config.yml`

- 修改`config.yml`，按照提示文本填写必要用户配置

下一步部署到云函数，不同家云函数的部署方法类似：

- 创建`函数服务`，选择`Python3`，`上传代码包`或者直接`上传文件夹`

- 设定`入口函数`为`index.main_handler`

- 设定`超时时间`300秒以上

- 创建`定时触发器`，参考cron表达式填写触发时间

  配置完毕，测试运行一下，OK
### C.部署到移动设备

在移动设备上安装`Termux`模拟终端运行，再参照A类型进行安装。

## FAQ

1. 设定经纬度之后，不知道正常定位应该显示的信息？

	- 运行`generateAddrString.py` 输入经纬度可以生成对应的模板定位信息
2. 为什么填好了配置文件运行报错`expected <block end>, but found <scalar>`？
   - yml文件严格规范空格缩进，注意检查文本是否对齐。

## 开源许可

[![License](https://img.shields.io/github/license/Jayve/JLAU-SignHelper?style=flat-square)](https://github.com/Jayve/JLAU-SignHelper/blob/main/LICENSE)