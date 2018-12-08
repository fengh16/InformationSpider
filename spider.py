import requests
from bs4 import BeautifulSoup
import config
import time
from email.mime.text import MIMEText
from email.header import Header
import os
import json
import datetime
import re
import traceback
from web_join import myjoin

cache_file = 'cache.txt'
got_article_data = set()
if os.path.exists(cache_file):
    with open(cache_file) as f:
        t = json.load(f)
        for i in t:
            got_article_data.add(i)
send_data = []

start_time = [int(i) for i in config.time_start.split('-')]


def accept_date(k):
    for i in range(3):
        if k[i] < start_time[i]:
            return False
    return True


def send_email():
    global send_data
    import smtplib

    with open(cache_file, 'w') as f2:
        t = []
        for i in got_article_data:
            t.append(i)
        json.dump(t, f2, indent=4)
    if len(send_data) == 0:
        print("没有找到监测的内容")
        return

    sender = config.email_sender
    receivers = [config.email_address]

    text = ''
    for i in send_data:
        text += '网址：%s 中找到了以下关键词：%s\r\n' % (i[1], ', '.join(i[0]))
    message = MIMEText(text, 'plain', 'utf-8')
    message['From'] = Header("Spider<%s>" % config.email_address, 'utf-8')  # 发送者
    message['To'] = Header("Receiver<%s>" % config.email_address, 'utf-8')  # 接收者

    subject = '监控提醒'
    message['Subject'] = Header(subject, 'utf-8')

    try:
        smtpObj = smtplib.SMTP()
        smtpObj.connect(config.email_host, 25)
        smtpObj.login(config.email_sender, config.email_password)
        smtpObj.sendmail(sender, receivers, message.as_string())
        print("邮件发送成功")
    except smtplib.SMTPException:
        print("Error: 无法发送邮件")


def get_web_info():
    global got_article_data, send_data
    try:
        for website in config.websites:
            need_next_page = True
            while need_next_page:
                print("正在查找网页 %s" % website)
                try:
                    a = requests.get(website)
                    a.encoding = 'utf-8'
                    if a.status_code != 200:
                        print("- 无法访问网页 %s" % website)
                        continue
                    # soup = BeautifulSoup(a.text, "html.parser")
                    # WTF什么垃圾政府网页……解析不了……垃圾…………………………………………………………………………………………
                    soup = BeautifulSoup(a.text, "html5lib")
                    next_page_href = soup.find_all('a', text='下一页')
                    list_data = soup.find_all('div', class_='zl_tabList')
                    if len(list_data) == 0:
                        list_data = soup.find_all('div', class_='newsList_01')
                        if len(list_data) == 0:
                            print("- 网页 %s 没有需要的数据" % website)
                            continue
                        articles_list = list_data[0].find_all('a')
                    else:
                        articles_list = list_data[0].find_all('ul')
                        if len(articles_list) == 0:
                            print("- 网页 %s 没有需要的数据" % website)
                            continue
                        if len(articles_list) == 1:
                            articles_list = articles_list[0].find_all('a')
                        else:
                            articles_list = list_data[0].find_all('a')
                    print("- 找到了文章列表，共%d篇" % len(articles_list))
                    count = 0
                    for article in articles_list:
                        target_website = myjoin(website, article.get('href'))
                        if target_website not in got_article_data:
                            try:
                                print("--- 正在检查文章 %s" % target_website)
                                count += 1
                                got_article_data.add(target_website)
                                date = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', str(article.parent))
                                if not date:
                                    date = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', str(article.parent.parent))
                                if not date:
                                    date = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', str(article.parent.parent.parent))
                                if date:
                                    if not accept_date([int(i) for i in [date.group(1), date.group(2), date.group(3)]]):
                                        need_next_page = False
                                        print("----- 日期不符合要求，跳过")
                                        continue
                                else:
                                    need_next_page = False
                                    print("----- 没有找到日期数据，跳过")
                                    continue
                                matched = []
                                time.sleep(config.web_interval_seconds)
                                article_web = requests.get(target_website)
                                article_web.encoding = 'utf-8'
                                soup = BeautifulSoup(article_web.text, "html.parser")
                                data = soup.find_all('div', class_='mainContent')
                                if len(data) == 0:
                                    print("--- 文章网页 %s 格式不对！" % target_website)
                                    continue
                                data = data[0].get_text()
                                for word in config.words:
                                    if word in data:
                                        matched.append(word)
                                if len(matched) > 0:
                                    send_data.append([matched, target_website])
                            except:
                                print("--- 文章网页 %s 访问出错！" % target_website)
                    print("-      其中有%d篇新文章" % count)
                    if need_next_page:
                        if len(next_page_href) != 1:
                            print("查找下一页标签出错！")
                        else:
                            website = myjoin(website, next_page_href[0].get('href'))
                            print("开始查找下一页，网址 %s" % website)
                    time.sleep(config.web_interval_seconds)
                except Exception as e:
                    print("- 访问网站 %s 出错" % website)
                    traceback.print_exc()
                    time.sleep(config.web_interval_seconds)
    except:
        print("get_web_info()运行出错！")
        time.sleep(config.web_interval_seconds)


if __name__ == '__main__':
    while True:
        send_data.clear()
        print("=================================")
        print("当前日期%s" % str(datetime.datetime.now()))
        get_web_info()
        send_email()
        print("此轮检查结束，休息%.2f秒，到%s再次检查" % (config.query_interval_seconds,
              str(datetime.datetime.now() + datetime.timedelta(0, config.query_interval_seconds))))
        time.sleep(config.query_interval_seconds)
