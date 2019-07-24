#!/root/anaconda3/bin/python
#-*-coding:utf-8-*-

import tushare as ts
import time
import json
import os
import requests
import smtplib
import datetime
import traceback
from email.mime.text import MIMEText

Folder_Path = 'config'

#配置文件json格式
'''
{
	"email": "example@email.com",
	"settings": {
		"price_up_to": [],
		"price_down_to": [{
			"stock": "603028",
			"price": "9.4"
		}],
		"price_up_percent": [],
		"price_down_percent": [],
		"five_minutes_price_up_percent": [],
		"five_minutes_price_down_percent": [{
			"stock": "603028",
			"price": "3"
		}]]
	}
}
'''

def get_day_type(query_date):
    # url = 'http://tool.bitefu.net/jiari/?d=' + query_date
    # 上面的url接口  工作日对应结果为 0, 休息日对应结果为 1, 节假日对应的结果为 2；
    # url = 'http://www.easybots.cn/api/holiday.php?d=' + query_date  需要实名认证
    url = 'http://api.goseek.cn/Tools/holiday?date=' + query_date
    # 返回数据：正常工作日对应结果为 0, 法定节假日对应结果为 1, 节假日调休补班对应的结果为 2，休息日对应结果为 3
    # 20190528
    response = requests.get(url=url,timeout=60)
    content = response.text  # str 类型的
    content = json.loads(content)
    # {"code":10000,"data":0}
    return content['data']
    # 返回数据：正常工作日对应结果为 0, 法定节假日对应结果为 1, 节假日调休补班对应的结果为 2，休息日对应结果为 3


def today_is_tradeday():
    query_date = datetime.datetime.strftime(datetime.datetime.today(), '%Y%m%d')
    #print(query_date)
    ret = None
    while ret is None:
        try:
            ret = get_day_type(query_date)
        except Exception:
            traceback.print_exc()
    return ret

def read_file(filename):
    with open(filename,'r') as f:
        s = f.read()
    return s

def get_realtime_price(stock):
    df = ts.get_realtime_quotes(stock)
    price = float(df[['price']].values[0][0])
    time = df[['time']].values[0][0]
    return price, time

def get_stock_name(stock):
    df = ts.get_realtime_quotes(stock)
    name = df[['name']].values[0][0]
    return name

def get_stock_pre_close(stock):
    df = ts.get_realtime_quotes(stock)
    pre_close = df[['pre_close']].values[0][0]
    return pre_close

def str_to_timestamp(dt):
    dt = str(datetime.datetime.now().date()) + " " + dt
    timeArray = time.strptime(dt, "%Y-%m-%d %H:%M:%S")
    # 转换成时间戳
    timestamp = time.mktime(timeArray)
    return timestamp

def pop_five_minutes_ago_data(l):
    def convert_to_absolute_timestamp(time):
        st = str_to_timestamp(time)
        if st > str_to_timestamp("12:00:00"):
            st = st - 60*60+30*60
        return st
    while len(l) > 0 and convert_to_absolute_timestamp(l[len(l)-1][1]) - convert_to_absolute_timestamp(l[0][1]) > 5*60:
        l.pop(0)

class Config:#传的所有文件都是不目录的，每个函数里自己补
    def __init__(self):
        self.lasttime = time.time()
        self.users = {}
        self.__config_path = Folder_Path+'/'
        self.stocks = set()
        self.load_config()

    def __for_each_config_files(self,f):#对于每个配置文件使用f处理一下
        files = os.listdir(self.__config_path)
        for file in files:
            f(file)

    def __load_file(self,file):#加载一个客户配置文件
        if os.path.splitext(file)[1] == '.json':
            try:
                dic = json.loads(read_file(self.__config_path+file))
                if 'email' in dic and 'settings' in dic and 'price_up_to' in dic['settings'] and 'price_down_to' in dic['settings']\
                        and 'price_up_percent' in dic['settings'] and 'price_down_percent' in dic['settings'] and 'five_minutes_price_up_percent' in dic['settings'] \
                        and 'five_minutes_price_down_percent' in dic['settings']:
                    self.users[file] = dic
            except Exception:
                traceback.print_exc()

    def __get_all_stocks(self):
        for filename in self.users:
            user = self.users[filename]
            for setting in user['settings'].keys():
                for item in user['settings'][setting]:
                    self.stocks.add(item['stock'])

    def __get_modified_files(self):
        files = os.listdir(self.__config_path)
        l = []
        for file in files:
            if os.stat(self.__config_path+file).st_mtime > self.lasttime:
                l.append(file)
        return l

    def load_config(self):
        self.users = {}
        self.lasttime = time.time()
        self.__for_each_config_files(self.__load_file)
        self.__get_all_stocks()

    def check_if_new_config(self):
        l = self.__get_modified_files()
        for file in l:
            self.__load_file(file)
            user = self.users[file]
            for setting in user['settings'].keys():
                for item in user['settings'][setting]:
                    self.stocks.add(item['stock'])
            self.lasttime = time.time()

    def write_back(self,l):
        flag = False
        for file in l:
            if os.stat(self.__config_path+file).st_mtime > self.lasttime:#如果要写回的文件发现有更新，则不处理
                continue
            flag = True
            with open(self.__config_path+file,'w') as f:
                json.dump(self.users[file],f)
        if flag:
            self.lasttime = time.time()


class Mail:
    def __init__(self):
        dic = json.loads(read_file(Folder_Path+'/mail.rc'))
        self.mail_host = dic['mail_host']
        # 163用户名
        self.mail_user = dic['mail_user']
        # 密码(部分邮箱为授权码)
        self.mail_pass = dic['mail_pass']
        # 邮件发送方邮箱地址
        self.sender = dic['sender']

    def send(self,Subject,receivers,content):
        # 设置email信息
        # 邮件内容设置
        message = MIMEText(content, 'plain', 'utf-8')
        # 邮件主题
        message['Subject'] = Subject
        # 发送方信息
        message['From'] = self.sender
        # 接受方信息
        message['To'] = receivers[0]
        # 登录并发送邮件
        try:
            smtpObj = smtplib.SMTP()
            # 连接到服务器
            smtpObj.connect(self.mail_host, 25)
            # 登录到服务器
            smtpObj.login(self.mail_user, self.mail_pass)
            # 发送
            smtpObj.sendmail(
                self.sender, receivers, message.as_string())
            # 退出
            smtpObj.quit()
            print('success')
        except smtplib.SMTPException as e:
            print('error', e)  # 打印错误

def update_stock(stocks,stocksdata):
    for stock in stocks:
        try:
            if stock not in stocksdata:
                stocksdata[stock] = {"name":get_stock_name(stock),"pre_close":float(get_stock_pre_close(stock)),'price':0,'five_mins_data':[]}
            data = get_realtime_price(stock)
            if not (len(stocksdata[stock]['five_mins_data']) > 0 and stocksdata[stock]['five_mins_data'][len(stocksdata[stock]['five_mins_data']) - 1] == data):
                stocksdata[stock]['price'] = data[0]
                stocksdata[stock]['five_mins_data'].append(data)
                pop_five_minutes_ago_data(stocksdata[stock]['five_mins_data'])
        except Exception:
            traceback.print_exc()
            continue

def remind_price_up_to(user,stocksdata,mail):
    ret = False
    for item in user['settings']['price_up_to']:
        if stocksdata[item['stock']]['price'] >= float(item['price']):
            mail.send(stocksdata[item['stock']]['name'] + '上涨到' + item['price'] + '了', user['email'],
                      "当前价格为" + str(stocksdata[item['stock']]['price']) + ",请及时查看")
            user['settings']['price_up_to'].remove(item)
            ret = True
    return ret

def remind_price_down_to(user,stocksdata,mail):
    ret = False
    for item in user['settings']['price_down_to']:
        if stocksdata[item['stock']]['price'] <= float(item['price']):
            mail.send(stocksdata[item['stock']]['name'] + '下跌到' + item['price'] + '了', user['email'],
                      "当前价格为" + str(stocksdata[item['stock']]['price']) + ",请及时查看")
            user['settings']['price_down_to'].remove(item)
            ret = True
    return ret

def remind_price_up_percent(user,stocksdata,mail):
    ret = False
    for item in user['settings']['price_up_percent']:
        if (stocksdata[item['stock']]['price'] - stocksdata[item['stock']]['pre_close']) / stocksdata[item['stock']][
            'pre_close'] >= float(item['price']) / 100:
            mail.send(stocksdata[item['stock']]['name'] + '上涨了' + item['price'] + '%', user['email'],
                      "当前价格为" + str(stocksdata[item['stock']]['price']) + ",请及时查看")
            user['settings']['price_up_percent'].remove(item)
            ret = True
    return ret

def remind_price_down_percent(user,stocksdata,mail):
    ret = False
    for item in user['settings']['price_down_percent']:
        if (stocksdata[item['stock']]['pre_close'] - stocksdata[item['stock']]['price']) / stocksdata[item['stock']][
            'pre_close'] >= float(item['price']) / 100:
            mail.send(stocksdata[item['stock']]['name'] + '下跌了' + item['price'] + '%', user['email'],
                      "当前价格为" + str(stocksdata[item['stock']]['price']) + ",请及时查看")
            user['settings']['price_down_percent'].remove(item)
            ret = True
    return ret

def remind_five_minutes_price_up_percent(user,stocksdata,mail):
    ret = False
    for item in user['settings']['five_minutes_price_up_percent']:
        mindata = min([x[0] for x in stocksdata[item['stock']]['five_mins_data']])
        if (stocksdata[item['stock']]['price'] - mindata)/mindata >= float(item['price'])/100:
            mail.send(stocksdata[item['stock']]['name'] + '五分钟内上涨了' + item['price'] + '%', user['email'],
                      "当前价格为" + str(stocksdata[item['stock']]['price']) + ",请及时查看")
            user['settings']['five_minutes_price_up_percent'].remove(item)
            ret = True
    return ret

def remind_five_minutes_price_down_percent(user,stocksdata,mail):
    ret = False
    for item in user['settings']['five_minutes_price_down_percent']:
        maxdata = max([x[0] for x in stocksdata[item['stock']]['five_mins_data']])
        if (maxdata - stocksdata[item['stock']]['price'])/maxdata >= float(item['price'])/100:
            mail.send(stocksdata[item['stock']]['name'] + '五分钟内下跌了' + item['price'] + '%', user['email'],
                      "当前价格为" + str(stocksdata[item['stock']]['price']) + ",请及时查看")
            user['settings']['five_minutes_price_down_percent'].remove(item)
            ret = True
    return ret

def inform_user(conf,stocksdata,mail):
    users = conf.users
    writeback = []
    for filename in users:
        user = users[filename]
        flag = False
        flag |= remind_price_up_to(user, stocksdata, mail)
        flag |= remind_price_down_to(user, stocksdata, mail)
        flag |= remind_price_up_percent(user, stocksdata, mail)
        flag |= remind_price_down_percent(user, stocksdata, mail)
        flag |= remind_five_minutes_price_up_percent(user, stocksdata, mail)
        flag |= remind_five_minutes_price_down_percent(user, stocksdata, mail)
        if flag:
            writeback.append(filename)
    if len(writeback)>0:
        conf.write_back(writeback)




if __name__ == '__main__':
    if today_is_tradeday() != 0:
        exit(0)
    if os.path.exists(Folder_Path) is False:
        os.makedirs(Folder_Path)
    mail = Mail()
    conf = Config()
    #conf.load_config()
    stocksdata = {}
    # 范围时间
    start_time = datetime.datetime.strptime(str(datetime.datetime.now().date()) + '9:25', '%Y-%m-%d%H:%M')
    stop_time = datetime.datetime.strptime(str(datetime.datetime.now().date()) + '15:35', '%Y-%m-%d%H:%M')
    launch_start_time = datetime.datetime.strptime(str(datetime.datetime.now().date()) + '11:30', '%Y-%m-%d%H:%M')
    launch_stop_time = datetime.datetime.strptime(str(datetime.datetime.now().date()) + '13:00', '%Y-%m-%d%H:%M')
    # 当前时间
    n_time = datetime.datetime.now()
    # 判断当前时间是否在范围时间内
    while n_time > start_time and n_time < stop_time:
        if n_time>launch_start_time and n_time <launch_stop_time:
            time.sleep(launch_stop_time-n_time)
        update_stock(conf.stocks,stocksdata)
        inform_user(conf, stocksdata, mail)
        #print(stocksdata)
        time.sleep(2)
        conf.check_if_new_config()
        n_time = datetime.datetime.now()
