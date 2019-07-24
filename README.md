# StockReminder
设定股票预警的功能

在配置文件里添加要预警的股票代码并设定提醒的值，触发后就会发送邮件提醒。

配置文件均在./config目录下，发送的邮箱配置需要卸载config/mail.rc里。
股票监控的文件为config/anyname.json,可以配置多个

system文件夹里为自动启动脚本，拷贝到systemd的目录下，修改启动的参数即可。
