#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 全部的handlers及一些辅助函数, 包括验证用户权限, 检查cookie等

import time
import re
import json
import logging
import hashlib
import base64
import asyncio
# import markdown2
from aiohttp import web
from coroweb import get, post # 导入装饰器,这样就能很方便的生成request handler
from models import Comment,User,Blog, next_id
# from apis import APIResourceNotFoundError, APIValueError, APIError, APIPermissionError, Page
from config import configs

#匹配邮箱与加密后面的正则表达式
_RE_EMAIL=re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1=re.compile(r'[0-9a-f]{40}$')


#取得页码
def get_page_index(page_str):
	p=1
	try:
		p=int(page_str)
	except ValueError as e:
		pass
	if p<1:
		p = 1
	return p

@get('/')
def index(request):
	summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
	logging.info('get开始：');
	blogs=[
		Blog(id='1',name='Text Blog',summary=summary,create_at=time.time()-120),
		Blog(id='2',name='Something New',summary=summary,create_at=time.time()-3600),
		Blog(id='3',name='Learn Swift',summary=summary,create_at=time.time()-7200)
	]
	# users = yield from User.findAll()
	# return {
	# 	'__template__':'test.html',
	# 	'users':users
	# }
	return {
		'__template__':'blogs.html',
		'blogs':blogs
	}

#API:获取用户信息
@get('/api/users')
def api_get_users(*,page='1'):
	page_index = get_page_index(page)
	num = yield from User.findNumber("count(id)")
	p=Page(num,page_index)
	if num==0:
		return dict(page=p,users=())
	users = yield from User.findAll(orderBy="created_at desc")
	print('返回用户列表:',users)
	for u in users:
		u.paasswd="******"
	 # 以dict形式返回,并且未指定__template__,将被app.py的response factory处理为json	
	return dict(page=p,users=users)	

#API:创建用户
@post('/api/users')
def api_register_user(*,name,email,passwd):
	#验证输入的正确性
	if not name or not name.strip():
		raise APIValueError("name")
	if not mail or not _RE_EMAIL.match(email):
		raise APIValueError("email")
	if not passwd or not _RE_SHA1.match(passwd):
		raise APIValueError("passwd")
	#查看是否存在该email
	# mysql parameters are listed in list
	users = yield from User.findAll('email=?',[email])	
	if len(users) >0:
		raise APIError('register:failed','email','Email is already in use')

	# 数据库内无相应的email信息,说明是第一次注册
	uid = next_id()
	sha1_passwd = '%s:%s' % (uid,passwd)
	# 将user id与密码的组合赋给sha1_passwd变量
    # 创建用户对象, 其中密码并不是用户输入的密码,而是经过复杂处理后的保密字符串
    # unicode对象在进行哈希运算之前必须先编码
    # sha1(secure hash algorithm),是一种不可逆的安全算法.这在一定程度上保证了安全性,因为用户密码只有用户一个人知道
    # hexdigest()函数将hash对象转换成16进制表示的字符串
    # md5是另一种安全算法
    # Gravatar(Globally Recognized Avatar)是一项用于提供在全球范围内使用的头像服务。只要在Gravatar的服务器上上传了你自己的头像，便可以在其他任何支持Gravatar的博客、论坛等地方使用它。此处image就是一个根据用户email生成的头像
	user = User(id-uid,name-name.strip(),email=email,passwd = hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(),image = "http://www.gravatar.com/avatar/%s?d=mm&s=120" % hashlib.md5(email.encode('utf-8')).hexdigest())
	yield from user.save()

	# 这其实还是一个handler,因此需要返回response. 此时返回的response是带有cookie的响应
	r=web.Response()
	# 刚创建的的用户设置cookiei(网站为了辨别用户身份而储存在用户本地终端的数据)
	# http协议是一种无状态的协议,即服务器并不知道用户上一次做了什么.
	# 因此服务器可以通过设置或读取Cookies中包含信息,借此维护用户跟服务器会话中的状态
	# user2cookie设置的是cookie的值
	# max_age是cookie的最大存活周期,单位是秒.当时间结束时,客户端将抛弃该cookie.之后需要重新登录
	r.set_cookid(COOKIE_NAME,user2cookie(user,600),max_age=600,httponly=True)	# 设置cookie最大存会时间为10min
	# r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)  #86400s=24h
	user.passwd = '******'	#修改密码外部显示为*
	# 设置content_type,将在data_factory中间件中继续处理
	r.content_type='application/json'
	# json.dumps方法将对象序列化为json格式
	r.body = json.dumps(user,ensure_ascii=False).encode('utf-8')
	return r

@get('/register')
def register():
		return {
			'__template__':'register.html'
		}	